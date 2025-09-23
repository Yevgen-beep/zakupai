class ComplianceSettings:
    # Ст.1: Исключения из сферы применения (для фильтра лотов)
    EXCLUDED_PROCUREMENTS = [
        "labor_contracts",  # услуги по трудовым договорам
        "non_entrepreneur_services",  # услуги физлиц без ИП
        "military_goods",  # военные товары/работы
        "international_projects",  # инвестиции от зарубежных банков/органов
        "national_holdings",  # холдинги, Нацбанк и т.д.
    ]
    REESTR_NEDOBRO_ENABLED = (
        True  # ст. 8: реестр недобросовестных (обновлено 15.09.2025)
    )
    AFFIL_CHECK_ENABLED = True  # ст. 7: аффилированность (запрет усилен)
    ANTI_DEMPING_THRESHOLD = 0.15  # ст. 13: демпинг >15%, доп. обеспечение
    COMPLAINT_DEADLINE_DAYS = 3  # ст. 25: жалобы — 3 дня, с pre-court
    SINGLE_SOURCE_LIST_ENABLED = (
        True  # Сентябрь 2025: новый перечень ТРУ для "из одного источника"
    )
    CANCEL_PROCEDURE_DAYS = (
        5  # Отмена/отказ: уведомление за 5 дней (обновление 7.09.2025)
    )
    TURNKEY_CONTEST_ENABLED = True  # Новый тип "под ключ" конкурсов (строительство)
    SINGLE_SOURCE_ENABLED = True  # Сентябрь 2025: закупки "из одного источника"
    SINGLE_SOURCE_LIST = [
        "bank_deposits",
        "credit_ratings",
        "scientific_research",
        "national_bank_services",
    ]
    AFFIL_BAN_IN_SINGLE_SOURCE = True  # Запрет аффилированности в прямых договорах
    RATING_AGENCY_THRESHOLD = "A-"  # Мин. рейтинг для инвестпроектов (S&P или аналог)
