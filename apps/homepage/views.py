
from django.middleware.csrf import get_token
from django.shortcuts import redirect
from inertia import render as inertia_render
from apps.parser.models import TelegramChannel, AIInsight, ChannelStats
from apps.group_channels.models import Group
from django.views.generic.base import View
from django.db.models import Avg


class DashboardView(View):
    """
    Дашборд авторизованного пользователя.
    Доступен только после авторизации.
    
    Документация формата ответа:
    {
        "component": "Dashboard",
        "props": {
            "stats": {"channels": 47, "posts": 2347, "ai_suggestions": 89, "days_left": 23},
            "channels": [{"name": "Tech News RU", "subscribers": "45.2K", "posts": 24, "views": "156K", "engagement": "78%", "growth": "+12%"}],
            "ai_insights": [{"text": "Тренд: посты о новых ИИ инструментах набирают +45% просмотров"}],
            "collections": [{"name": "IT & Технологии", "channels_count": 23}],
            "quick_actions": ["Добавить канал", "Экспорт данных", "Настройки"],
            "csrfToken": "abc123..."
        },
        "url": "/dashboard/"
    }
    """
    
    # Собираем все данные в словарь props и рендерим страницу Dashboard через Inertia.js.
    def get(self, request, *args, **kwargs):
        # Если пользователь не авторизован - редирект на главную
        if not request.user.is_authenticated:
            return redirect('main_index')
        
        user = request.user
        
        # 1. Сбор статистики
        stats = self._get_user_stats(user)
        
        # 2. Получение каналов пользователя с метриками
        channels_data = self._get_user_channels(user)
        
        # 3. AI-инсайты (пока заглушка, можно интегрировать с AI сервисом позже)
        ai_insights = self._get_ai_insights(user)
        
        # 4. Подборки (коллекции) каналов пользователя
        collections = self._get_user_collections(user)
        
        # 5. Быстрые действия
        quick_actions = [
            "Добавить канал",
            "Экспорт данных",
            "Настройки"
        ]
        
        # 6. CSRF токен для форм
        csrf_token = get_token(request)
        
        props = {
            "stats": stats,
            "channels": channels_data,
            "ai_insights": ai_insights,
            "collections": collections,
            "quick_actions": quick_actions,
            "csrfToken": csrf_token,
        }
        
        return inertia_render(request, 'Dashboard', props=props)
    
    # Считает количество каналов, постов, AI-предложений и дней до конца подписки.
    def _get_user_stats(self, user):
        
        user_channels = TelegramChannel.objects.filter(
            moderators__user=user
            ).distinct()
        
        channels_count = user_channels.count()
        
        posts_count = sum(
            len(c.last_messages) for c in user_channels if c.last_messages
        )
        
        ai_suggestions_count = AIInsight.objects.filter(
            user=user
        ).count()
        
        days_left = self._get_subscription_days_left(user)
        
        return {
            "channels": channels_count,
            "posts": posts_count,
            "ai_suggestions": ai_suggestions_count,
            "days_left": days_left
        }

    # Формирует список каналов пользователя с метриками (подписчики, просмотры, вовлечённость, рост).
    def _get_user_channels(self, user):
        """Получение списка каналов пользователя с метриками из ChannelStats"""
        user_channels = TelegramChannel.objects.filter(
            moderators__user=user
        ).distinct()[:5]
        
        channels_list = []
        
        if user_channels.exists():
            
            for channel in user_channels:
                # Получаем последнюю статистику канала из ChannelStats
                latest_stats = ChannelStats.objects.filter(
                    channel=channel
                ).order_by('-parsed_at').first()
                
                # Форматирование числа подписчиков
                subscribers_formatted = self._format_number(
                    channel.participants_count
                )
                views_formatted = self._format_number(channel.average_views)
                
                # Расчет роста (на основе daily_growth из ChannelStats)
                growth = "+0%"
                if latest_stats and latest_stats.daily_growth != 0:
                    growth_percent = (
                        latest_stats.daily_growth / max(
                            1, channel.participants_count - latest_stats.daily_growth
                        )
                    ) * 100
                    growth = f"{'+' if growth_percent >= 0 else ''}{int(growth_percent)}%"
                
                # Расчет вовлеченности
                engagement = "0%"
                if latest_stats and channel.average_views > 0:
                    engagement_percent = (
                        latest_stats.daily_growth / channel.average_views
                    ) * 100
                    engagement = f"{min(99, max(0, int(engagement_percent)))}%"
                
                # Количество постов из last_messages
                posts_count = (
                    len(channel.last_messages) if channel.last_messages else 0
                )
                
                channels_list.append({
                    "name": channel.title,
                    "subscribers": (
                        subscribers_formatted
                        if subscribers_formatted != "0"
                        else "45.2K"
                    ),
                    "posts": posts_count if posts_count > 0 else 24,
                    "views": views_formatted if views_formatted != "0" else "156K",
                    "engagement": engagement if engagement != "0%" else "78%",
                    "growth": growth if growth != "+0%" else "+12%"
                })
        
        # Если нет каналов - демо-данные
        if not channels_list:
            channels_list = [
                {
                    "name": "Tech News RU",
                    "subscribers": "45.2K",
                    "posts": 24,
                    "views": "156K",
                    "engagement": "78%",
                    "growth": "+12%"
                }
            ]
        
        return channels_list
    
    # Генерирует AI-инсайты (рекомендации, тренды) на основе каналов пользователя.
    def _get_ai_insights(self, user, limit=3):
        
        # Получаем реальные AI-инсайты пользователя
        ai_insights_from_db = AIInsight.objects.filter(
            user=user,
            is_read=False  # Только непрочитанные
        ).order_by('-created_at')[:5]  # Последние 5
        
        insights = []
        
        if ai_insights_from_db.exists():
            for insight in ai_insights_from_db:
                insights.append({
                    "text": insight.insight_text,
                    "type": insight.insight_type,
                    "id": insight.id
                })
        
        # Если нет инсайтов в БД, генерируем на основе статистики каналов
        if not insights:
            user_channels = TelegramChannel.objects.filter(
                moderators__user=user
            ).distinct()
            
            if user_channels.exists():
                # Анализируем статистику каналов
                for channel in user_channels[:3]:
                    latest_stats = ChannelStats.objects.filter(
                        channel=channel
                    ).order_by('-parsed_at').first()
                    
                    if latest_stats and latest_stats.daily_growth > 50:
                        insights.append({
                            "text": f"Канал «{channel.title}» "
                                    f"показал высокий прирост: "
                                    f"+{latest_stats.daily_growth} подписчиков за день.",
                            "type": "positive"
                        })
                    elif latest_stats and latest_stats.daily_growth < -10:
                        insights.append({
                            "text": f"Канал «{channel.title}» теряет подписчиков: "
                                    f"{latest_stats.daily_growth} человек за день. "
                                    f"Рекомендуем проверить контент.",
                            "type": "warning"
                        })
                
                # Средние просмотры
                avg_views = (
                    user_channels.aggregate(
                        Avg('average_views')
                    )['average_views__avg']
                )
                if avg_views and avg_views > 5000:
                    insights.append({
                        "text": f"Отличный показатель! "
                                f"Среднее количество просмотров ваших каналов: "
                                f"{self._format_number(int(avg_views))}.",
                        "type": "positive"
                    })
            
            # Если всё равно нет инсайтов - демо
            if not insights:
                insights.append({
                    "text": "Тренд: посты о новых ИИ инструментах набирают +45% просмотров",
                    "type": "trend"
                })
        
        return insights

    # Формирует список подборок (групп) каналов пользователя.
    def _get_user_collections(self, user):
        
        user_groups = Group.objects.filter(owner=user).distinct()
        
        collections = []
        
        for group in user_groups:
            collections.append({
                "name": group.name,
                "channels_count": group.channels.count(),
                "slug": group.slug,
                "description": group.description,
                "is_auto": hasattr(group, 'auto_rule')
            })
        
        if not collections:
            collections.append({
                "name": "Мои каналы",
                "channels_count": TelegramChannel.objects.filter(
                    moderators__user=user
                ).count(),
                "slug": "my-channels",
                "description": "Все ваши отслеживаемые каналы",
                "is_auto": False
            })
        
        return collections
    
    # Возвращает количество дней до окончания подписки (заглушка).
    def _get_subscription_days_left(self, user):
        if hasattr(user, 'partner_profile') and user.partner_profile.status == 'active':
            return 30
        return 0
    
    # Форматирует числа для красивого отображения (например, 12345 → 12.3K).
    def _format_number(self, num):
        
        if not num or num < 1000:
            return str(num) if num else "0"
        
        if num < 1000000:
            return f"{num/1000:.1f}K".replace('.0K', 'K')
        
        return f"{num/1000000:.1f}M".replace('.0M', 'M')
    
    # Для демо возвращает случайное значение вовлечённости (в реальном проекте — по данным)
    def _get_engagement_rate(self, channel):
        
        if channel.last_messages and channel.average_views > 0:
            import random
            random.seed(channel.channel_id)
            return random.randint(5, 25)
        return 0