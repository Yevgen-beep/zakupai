# Полная документация GraphQL API государственных закупок Казахстана

## 🚀 Базовая информация

- **URL**: `https://ows.goszakup.gov.kz/v3/graphql`
- **Метод**: `POST`
- **Аутентификация**: `Authorization: Bearer <токен>`
- **Content-Type**: `application/json`

## 📋 Основные сущности

### 1. **Lots (Лоты)** - 28,309,104 записей

Информация о лотах в торгах/закупках.

**CURL для получения списка:**

```bash
curl -X POST https://ows.goszakup.gov.kz/v3/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer cc9ae7eb4025aca71e2e445823d88b86" \
  -d '{
    "query": "{ Lots(limit: 5) { id nameRu descriptionRu amount trdBuyId trdBuyNumberAnno lastUpdateDate RefLotsStatus { nameRu } Customer { nameRu bin } } }"
  }'
```

**Основные поля:**

- `id` (Int) - ID лота
- `nameRu` (String) - Название на русском
- `nameKz` (String) - Название на казахском
- `descriptionRu` (String) - Описание на русском
- `amount` (Float) - Сумма лота
- `trdBuyId` (Int) - ID связанной торговой процедуры
- `trdBuyNumberAnno` (String) - Номер торговой процедуры
- `lastUpdateDate` (String) - Дата последнего обновления

**Фильтры (`LotsFiltersInput`):**

- `nameRu` (String) - Поиск по названию
- `descriptionRu` (String) - Поиск по описанию
- `amount` ([Float]) - Диапазон сумм
- `customerId` (Int) - ID заказчика
- `trdBuyId` ([Int]) - ID торговых процедур

**CURL с фильтром:**

```bash
curl -X POST https://ows.goszakup.gov.kz/v3/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer cc9ae7eb4025aca71e2e445823d88b86" \
  -d '{
    "query": "{ Lots(filter: { nameRu: \"бензин\" }, limit: 5) { id nameRu descriptionRu amount trdBuyNumberAnno Customer { nameRu } } }"
  }'
```

**Связи:**

- `Customer` → `Subject` (заказчик)
- `TrdBuy` → `TrdBuy` (торговая процедура)
- `RefLotsStatus` → статус лота
- `Plans` → связанные планы закупок

______________________________________________________________________

### 2. **TrdBuy (Торговые процедуры)** - 11,094,120 записей

Информация о торговых процедурах/объявлениях о закупках.

**CURL для получения списка:**

```bash
curl -X POST https://ows.goszakup.gov.kz/v3/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer cc9ae7eb4025aca71e2e445823d88b86" \
  -d '{
    "query": "{ TrdBuy(limit: 3) { id numberAnno nameRu totalSum publishDate RefBuyStatus { nameRu } Organizer { nameRu bin } Lots { id nameRu amount } } }"
  }'
```

**Основные поля:**

- `id` (Int) - ID торговой процедуры
- `numberAnno` (String) - Номер объявления
- `nameRu` (String) - Наименование закупки
- `totalSum` (Float) - Общая сумма
- `publishDate` (String) - Дата публикации
- `startDate` (String) - Дата начала приема заявок
- `endDate` (String) - Дата окончания приема заявок

**Фильтры (`TrdBuyFiltersInput`):**

- `nameRu` (String) - Поиск по названию
- `numberAnno` (String) - По номеру объявления
- `totalSum` ([Float]) - Диапазон сумм
- `orgPid` ([Int]) - ID организаторов
- `refBuyStatusId` ([Int]) - Статусы закупок
- `publishDate` ([String]) - Даты публикации
- `kato` ([String]) - Коды КАТО

**CURL с фильтрами:**

```bash
curl -X POST https://ows.goszakup.gov.kz/v3/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer cc9ae7eb4025aca71e2e445823d88b86" \
  -d '{
    "query": "{ TrdBuy(filter: { totalSum: [1000000, 5000000] }, limit: 3) { id nameRu totalSum publishDate RefBuyStatus { nameRu } Organizer { nameRu } } }"
  }'
```

**Связи:**

- `Organizer` → `Subject` (организатор)
- `Lots` → `[Lots]` (лоты)
- `RefBuyStatus` → статус закупки
- `RefTradeMethods` → способ закупки

______________________________________________________________________

### 3. **Contract (Контракты)** - 18,228,926 записей

Информация о заключенных контрактах.

**CURL для получения списка:**

```bash
curl -X POST https://ows.goszakup.gov.kz/v3/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer cc9ae7eb4025aca71e2e445823d88b86" \
  -d '{
    "query": "{ Contract(limit: 2) { id contractNumber contractSum signDate customerBin supplierBiin Customer { nameRu bin } Supplier { nameRu bin } RefContractStatus { nameRu } } }"
  }'
```

**Основные поля:**

- `id` (Int) - ID контракта
- `contractNumber` (String) - Номер контракта
- `contractSum` (Float) - Сумма контракта
- `signDate` (String) - Дата подписания
- `customerBin` (String) - БИН заказчика
- `supplierBiin` (String) - БИН/ИИН поставщика
- `planExecDate` (String) - Планируемая дата исполнения
- `faktExecDate` (String) - Фактическая дата исполнения

**Связи:**

- `Customer` → `Subject` (заказчик)
- `Supplier` → `Subject` (поставщик)
- `TrdBuy` → `TrdBuy` (связанная торговая процедура)
- `RefContractStatus` → статус контракта
- `Acts` → акты приемки работ

______________________________________________________________________

### 4. **Subjects (Субъекты)** - 496,931 записей

Информация об участниках системы государственных закупок.

**CURL для получения списка:**

```bash
curl -X POST https://ows.goszakup.gov.kz/v3/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer cc9ae7eb4025aca71e2e445823d88b86" \
  -d '{
    "query": "{ Subjects(limit: 2) { pid bin nameRu fullNameRu lastUpdateDate Address { address katoCode RefKato { nameRu } } } }"
  }'
```

**Основные поля:**

- `pid` (Int) - ID участника
- `bin` (String) - БИН организации
- `iin` (String) - ИИН физлица
- `nameRu` (String) - Краткое наименование
- `fullNameRu` (String) - Полное наименование
- `email` (String) - Email
- `phone` (String) - Телефон

**Фильтры (`SubjectFiltersInput`):**

- `nameRu` (String) - Поиск по названию
- `bin` (String) - По БИН
- `iin` (String) - По ИИН
- `katoList` (String) - По КАТО

**CURL с фильтром по БИН:**

```bash
curl -X POST https://ows.goszakup.gov.kz/v3/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer cc9ae7eb4025aca71e2e445823d88b86" \
  -d '{
    "query": "{ Subjects(filter: { bin: \"050340002362\" }, limit: 1) { pid bin nameRu fullNameRu Address { address katoCode RefKato { nameRu } } } }"
  }'
```

**Связи:**

- `Address` → `[SubjectAddress]` (адреса)
- `Employees` → `[SubjectUsers]` (сотрудники)
- `RefCountries` → справочник стран

______________________________________________________________________

### 5. **Rnu (Реестр недобросовестных участников)** - 19,779 записей

Информация о недобросовестных поставщиках.

**CURL для получения списка:**

```bash
curl -X POST https://ows.goszakup.gov.kz/v3/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer cc9ae7eb4025aca71e2e445823d88b86" \
  -d '{
    "query": "{ Rnu(limit: 2) { id supplierNameRu supplierBiin startDate endDate katoList Supplier { nameRu bin } } }"
  }'
```

**Основные поля:**

- `id` (Int) - ID записи
- `supplierNameRu` (String) - Наименование поставщика
- `supplierBiin` (String) - БИН/ИИН поставщика
- `startDate` (String) - Дата включения в реестр
- `endDate` (String) - Дата исключения из реестра
- `katoList` ([Int]) - Коды КАТО

______________________________________________________________________

### 6. **Plans (Планы закупок)** - 39,927,126 записей

Информация о планах государственных закупок.

**CURL для получения списка:**

```bash
curl -X POST https://ows.goszakup.gov.kz/v3/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer cc9ae7eb4025aca71e2e445823d88b86" \
  -d '{
    "query": "{ Plans(limit: 1) { id nameRu amount refTradeMethodsId Customer { pid nameRu bin } RefTradeMethods { nameRu } } }"
  }'
```

______________________________________________________________________

## 🔧 Ограничения и особенности

### Пагинация

- **Максимальный лимит**: 200 записей за запрос
- **Параметры**: `limit` (до 200), `after` (ID записи для следующей страницы)
- **Пример пагинации:**

```bash
curl -X POST https://ows.goszakup.gov.kz/v3/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer cc9ae7eb4025aca71e2e445823d88b86" \
  -d '{
    "query": "{ Lots(limit: 200, after: 37932298) { id nameRu amount lastUpdateDate } }"
  }'
```

### Аутентификация

- **Ошибка 403**: При неверном токене

```bash
# Ошибка аутентификации
curl -X POST https://ows.goszakup.gov.kz/v3/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer invalid_token" \
  -d '{ "query": "{ Lots(limit: 1) { id } }" }'
```

### Производительность

- **Время ответа**: ~1 сек для сложных запросов
- **Без сортировки**: API не поддерживает параметр `order`
- **Глубокие связи**: Поддерживаются вложенные запросы до 3-4 уровней

______________________________________________________________________

## 🔗 Основные связи между сущностями

```
TrdBuy (Торговая процедура)
├── Lots[] (Лоты)
│   ├── Customer → Subject (Заказчик)
│   ├── Plans[] → PlnPoint (Планы)
│   └── RefLotsStatus (Статус лота)
├── Organizer → Subject (Организатор)
├── RefBuyStatus (Статус закупки)
└── RefTradeMethods (Способ закупки)

Contract (Контракт)
├── Customer → Subject (Заказчик)
├── Supplier → Subject (Поставщик)
├── TrdBuy → TrdBuy (Торговая процедура)
├── RefContractStatus (Статус контракта)
└── Acts[] → ContractAct (Акты)

Subject (Субъект)
├── Address[] → SubjectAddress
│   └── RefKato (Справочник КАТО)
├── Employees[] → SubjectUsers
└── RefCountries (Справочник стран)
```

______________________________________________________________________

## ⚡ Примеры сложных запросов

### Поиск лотов с полной информацией о заказчике и торгах:

```bash
curl -X POST https://ows.goszakup.gov.kz/v3/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer cc9ae7eb4025aca71e2e445823d88b86" \
  -d '{
    "query": "{ TrdBuy(limit: 1) { id numberAnno nameRu Lots { id nameRu amount trdBuyId Customer { nameRu bin pid } TrdBuy { id nameRu } } Organizer { pid nameRu bin } } }"
  }'
```

### Поиск контрактов с информацией о торгах и лотах:

```bash
curl -X POST https://ows.goszakup.gov.kz/v3/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer cc9ae7eb4025aca71e2e445823d88b86" \
  -d '{
    "query": "{ Contract(limit: 1) { id contractNumber contractSum Customer { pid nameRu bin } Supplier { pid nameRu bin } TrdBuy { id nameRu numberAnno Lots { id nameRu } } } }"
  }'
```

______________________________________________________________________

## 📈 Статистика API

- **Общее количество записей**: 135+ млн

- **Основные коллекции**:

  - Plans: 39,927,126
  - Lots: 28,309,104
  - Contract: 18,228,926
  - TrdBuy: 11,094,120
  - Subjects: 496,931
  - Rnu: 19,779

- **Лимиты**: максимум 200 записей за запрос

- **Время отклика**: 0.5-1.5 секунды

- **Аутентификация**: Bearer токен обязателен

- **Сортировка**: не поддерживается (только по ID по умолчанию)

- **Фильтрация**: поддерживается по большинству полей

Документация предоставляет полный набор CURL команд для работы с API государственных закупок Казахстана, включая все основные сущности, их поля, фильтры, связи и ограничения.

______________________________________________________________________

# PostgreSQL Database Schema for Goszakup ETL

## ER-модель

### Основные связи:

- Lots --(trdBuyId)--> TrdBuy
- Lots --(customerId)--> Subjects(pid)
- TrdBuy --(orgPid)--> Subjects(pid)
- Contract --(customerBin)--> Subjects(bin)
- Contract --(supplierBiin)--> Subjects(bin/iin)
- Contract --(trdBuyId)--> TrdBuy
- Plans --(sysSubjectsId)--> Subjects(pid)
- Rnu --(supplierBiin)--> Subjects(bin/iin)
- SubjectAddress --(pid)--> Subjects(pid)
- SubjectAddress --(katoCode)--> RefKato(code)

## PostgreSQL SQL Schema

```sql
-- Справочники
CREATE TABLE ref_buy_status (
    id INTEGER PRIMARY KEY,
    name_ru TEXT,
    name_kz TEXT,
    code TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE ref_trade_methods (
    id INTEGER PRIMARY KEY,
    name_ru TEXT,
    name_kz TEXT,
    code TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE ref_contract_status (
    id INTEGER PRIMARY KEY,
    name_ru TEXT,
    name_kz TEXT,
    code TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE ref_lots_status (
    id INTEGER PRIMARY KEY,
    name_ru TEXT,
    name_kz TEXT,
    code TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE ref_kato (
    code TEXT PRIMARY KEY,
    name_ru TEXT,
    name_kz TEXT,
    full_name_ru TEXT,
    full_name_kz TEXT,
    level INTEGER,
    parent_code TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE ref_countries (
    code TEXT PRIMARY KEY,
    code2 TEXT,
    code3 TEXT,
    name_ru TEXT,
    name_kz TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Основные сущности
CREATE TABLE subjects (
    pid INTEGER PRIMARY KEY,
    bin TEXT UNIQUE,
    iin TEXT,
    inn TEXT,
    unp TEXT,
    name_ru TEXT,
    name_kz TEXT,
    full_name_ru TEXT,
    full_name_kz TEXT,
    email TEXT,
    phone TEXT,
    website TEXT,
    reg_date TIMESTAMP,
    last_update_date TIMESTAMP,
    country_code TEXT REFERENCES ref_countries(code),
    qvazi INTEGER DEFAULT 0,
    customer INTEGER DEFAULT 0,
    organizer INTEGER DEFAULT 0,
    supplier INTEGER DEFAULT 0,
    type_supplier INTEGER,
    system_id INTEGER,
    index_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE subject_addresses (
    id INTEGER PRIMARY KEY,
    pid INTEGER NOT NULL REFERENCES subjects(pid) ON DELETE CASCADE,
    address_type INTEGER,
    address TEXT,
    kato_code TEXT REFERENCES ref_kato(code),
    phone TEXT,
    country_code TEXT REFERENCES ref_countries(code),
    date_create TIMESTAMP,
    edit_date TIMESTAMP,
    system_id INTEGER,
    index_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE trdbuy (
    id INTEGER PRIMARY KEY,
    number_anno TEXT UNIQUE NOT NULL,
    name_ru TEXT,
    name_kz TEXT,
    total_sum DECIMAL(20,2),
    count_lots INTEGER DEFAULT 0,
    ref_trade_methods_id INTEGER REFERENCES ref_trade_methods(id),
    ref_subject_type_id INTEGER,
    customer_bin TEXT,
    customer_pid INTEGER REFERENCES subjects(pid),
    customer_name_kz TEXT,
    customer_name_ru TEXT,
    org_bin TEXT,
    org_pid INTEGER REFERENCES subjects(pid),
    org_name_kz TEXT,
    org_name_ru TEXT,
    ref_buy_status_id INTEGER REFERENCES ref_buy_status(id),
    start_date TIMESTAMP,
    repeat_start_date TIMESTAMP,
    repeat_end_date TIMESTAMP,
    end_date TIMESTAMP,
    publish_date TIMESTAMP,
    itogi_date_public TIMESTAMP,
    last_update_date TIMESTAMP,
    fin_year INTEGER[],
    kato TEXT[],
    system_id INTEGER,
    index_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) PARTITION BY RANGE (publish_date);

-- Партиции для TrdBuy по годам
CREATE TABLE trdbuy_2023 PARTITION OF trdbuy
    FOR VALUES FROM ('2023-01-01') TO ('2024-01-01');
CREATE TABLE trdbuy_2024 PARTITION OF trdbuy
    FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
CREATE TABLE trdbuy_2025 PARTITION OF trdbuy
    FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');

CREATE TABLE lots (
    id INTEGER PRIMARY KEY,
    lot_number TEXT,
    ref_lot_status_id INTEGER REFERENCES ref_lots_status(id),
    last_update_date TIMESTAMP,
    union_lots INTEGER DEFAULT 0,
    count DECIMAL(20,4),
    amount DECIMAL(20,2),
    name_ru TEXT,
    name_kz TEXT,
    description_ru TEXT,
    description_kz TEXT,
    customer_id INTEGER REFERENCES subjects(pid),
    customer_bin TEXT,
    customer_name_ru TEXT,
    customer_name_kz TEXT,
    trdbuy_number_anno TEXT,
    trdbuy_id INTEGER NOT NULL,
    dumping INTEGER DEFAULT 0,
    ref_trade_methods_id INTEGER REFERENCES ref_trade_methods(id),
    psd_sign INTEGER DEFAULT 0,
    consulting_services INTEGER DEFAULT 0,
    point_list INTEGER[],
    enstru_list INTEGER[],
    pln_point_kato_list TEXT[],
    singl_org_sign INTEGER DEFAULT 0,
    is_light_industry INTEGER DEFAULT 0,
    is_construction_work INTEGER DEFAULT 0,
    is_deleted INTEGER DEFAULT 0,
    system_id INTEGER,
    index_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trdbuy_id, trdbuy_number_anno) REFERENCES trdbuy(id, number_anno) ON DELETE CASCADE
) PARTITION BY RANGE (last_update_date);

-- Партиции для Lots по годам
CREATE TABLE lots_2023 PARTITION OF lots
    FOR VALUES FROM ('2023-01-01') TO ('2024-01-01');
CREATE TABLE lots_2024 PARTITION OF lots
    FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
CREATE TABLE lots_2025 PARTITION OF lots
    FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');

CREATE TABLE contracts (
    id INTEGER PRIMARY KEY,
    parent_id INTEGER,
    root_id INTEGER,
    trdbuy_id INTEGER REFERENCES trdbuy(id),
    trdbuy_number_anno TEXT,
    trdbuy_name_ru TEXT,
    trdbuy_name_kz TEXT,
    ref_contract_status_id INTEGER REFERENCES ref_contract_status(id),
    deleted INTEGER DEFAULT 0,
    crdate TIMESTAMP,
    last_update_date TIMESTAMP,
    supplier_id INTEGER REFERENCES subjects(pid),
    supplier_biin TEXT,
    supplier_bik TEXT,
    supplier_iik TEXT,
    supplier_bank_name_kz TEXT,
    supplier_bank_name_ru TEXT,
    supplier_legal_address TEXT,
    customer_id INTEGER REFERENCES subjects(pid),
    customer_bin TEXT,
    customer_bik TEXT,
    customer_iik TEXT,
    customer_bank_name_kz TEXT,
    customer_bank_name_ru TEXT,
    customer_legal_address TEXT,
    contract_number TEXT,
    contract_number_sys TEXT,
    payments_terms_ru TEXT,
    payments_terms_kz TEXT,
    ref_subject_type_id INTEGER,
    is_gu INTEGER DEFAULT 0,
    fin_year INTEGER,
    ref_contract_agr_form_id INTEGER,
    ref_contract_year_type_id INTEGER,
    ref_finsource_id INTEGER,
    ref_currency_code TEXT,
    exchange_rate DECIMAL(10,4),
    contract_sum DECIMAL(20,2),
    contract_sum_wnds DECIMAL(20,2),
    sign_date TIMESTAMP,
    ec_end_date TIMESTAMP,
    plan_exec_date TIMESTAMP,
    fakt_exec_date TIMESTAMP,
    fakt_sum DECIMAL(20,2),
    fakt_sum_wnds DECIMAL(20,2),
    contract_end_date TIMESTAMP,
    ref_contract_cancel_id INTEGER,
    ref_contract_type_id INTEGER,
    description_kz TEXT,
    description_ru TEXT,
    fakt_trade_methods_id INTEGER REFERENCES ref_trade_methods(id),
    with_nds INTEGER DEFAULT 0,
    enforcement INTEGER DEFAULT 0,
    system_id INTEGER,
    index_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) PARTITION BY RANGE (sign_date);

-- Партиции для Contracts по годам
CREATE TABLE contracts_2023 PARTITION OF contracts
    FOR VALUES FROM ('2023-01-01') TO ('2024-01-01');
CREATE TABLE contracts_2024 PARTITION OF contracts
    FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
CREATE TABLE contracts_2025 PARTITION OF contracts
    FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');

CREATE TABLE plans (
    id INTEGER PRIMARY KEY,
    rootrecord_id INTEGER,
    sys_subjects_id INTEGER REFERENCES subjects(pid),
    sys_organizator_id INTEGER REFERENCES subjects(pid),
    subject_biin TEXT,
    subject_name_ru TEXT,
    subject_name_kz TEXT,
    name_ru TEXT,
    name_kz TEXT,
    ref_trade_methods_id INTEGER REFERENCES ref_trade_methods(id),
    ref_units_code TEXT,
    code_gu TEXT,
    count DECIMAL(20,4),
    price DECIMAL(20,2),
    amount DECIMAL(20,2),
    ref_months_id INTEGER,
    ref_pln_point_status_id INTEGER,
    pln_point_year INTEGER,
    ref_subject_type_id INTEGER,
    ref_enstru_code TEXT,
    ref_enstru_id INTEGER,
    ref_finsource_id INTEGER,
    ref_abp_code INTEGER,
    is_qvazi INTEGER DEFAULT 0,
    date_create TIMESTAMP,
    timestamp_field TIMESTAMP,
    ref_point_type_id INTEGER,
    desc_ru TEXT,
    desc_kz TEXT,
    extra_desc_kz TEXT,
    extra_desc_ru TEXT,
    sum1 DECIMAL(20,2),
    sum2 DECIMAL(20,2),
    sum3 DECIMAL(20,2),
    supply_date_ru TEXT,
    prepayment DECIMAL(20,2),
    ref_justification_id INTEGER,
    ref_amendment_agreem_type_id INTEGER,
    ref_amendm_agreem_justif_id INTEGER,
    contract_prev_point_id INTEGER,
    transfer_sys_subjects_id INTEGER,
    transfer_type INTEGER,
    ref_budget_type_id INTEGER,
    createdin_act_id INTEGER,
    is_active INTEGER DEFAULT 1,
    active_act_id INTEGER,
    is_deleted INTEGER DEFAULT 0,
    system_id INTEGER,
    index_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) PARTITION BY RANGE (date_create);

-- Партиции для Plans по годам
CREATE TABLE plans_2023 PARTITION OF plans
    FOR VALUES FROM ('2023-01-01') TO ('2024-01-01');
CREATE TABLE plans_2024 PARTITION OF plans
    FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
CREATE TABLE plans_2025 PARTITION OF plans
    FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');

CREATE TABLE rnu (
    id INTEGER PRIMARY KEY,
    pid INTEGER REFERENCES subjects(pid),
    supplier_name_ru TEXT,
    supplier_name_kz TEXT,
    supplier_biin TEXT,
    supplier_innunp TEXT,
    system_id INTEGER,
    start_date TIMESTAMP,
    end_date TIMESTAMP,
    supplier TEXT,
    kato_list INTEGER[],
    index_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Индексы
CREATE INDEX CONCURRENTLY idx_subjects_bin ON subjects(bin) WHERE bin IS NOT NULL;
CREATE INDEX CONCURRENTLY idx_subjects_iin ON subjects(iin) WHERE iin IS NOT NULL;
CREATE INDEX CONCURRENTLY idx_subjects_name_ru ON subjects(name_ru);
CREATE INDEX CONCURRENTLY idx_subjects_last_update ON subjects(last_update_date);

CREATE INDEX CONCURRENTLY idx_trdbuy_publish_date ON trdbuy(publish_date);
CREATE INDEX CONCURRENTLY idx_trdbuy_org_pid ON trdbuy(org_pid);
CREATE INDEX CONCURRENTLY idx_trdbuy_customer_pid ON trdbuy(customer_pid);
CREATE INDEX CONCURRENTLY idx_trdbuy_status ON trdbuy(ref_buy_status_id);
CREATE INDEX CONCURRENTLY idx_trdbuy_name_ru ON trdbuy USING gin(to_tsvector('russian', name_ru));

CREATE INDEX CONCURRENTLY idx_lots_trdbuy_id ON lots(trdbuy_id);
CREATE INDEX CONCURRENTLY idx_lots_customer_id ON lots(customer_id);
CREATE INDEX CONCURRENTLY idx_lots_update_date ON lots(last_update_date);
CREATE INDEX CONCURRENTLY idx_lots_name_ru ON lots USING gin(to_tsvector('russian', name_ru));

CREATE INDEX CONCURRENTLY idx_contracts_sign_date ON contracts(sign_date);
CREATE INDEX CONCURRENTLY idx_contracts_customer_id ON contracts(customer_id);
CREATE INDEX CONCURRENTLY idx_contracts_supplier_id ON contracts(supplier_id);
CREATE INDEX CONCURRENTLY idx_contracts_trdbuy_id ON contracts(trdbuy_id);

CREATE INDEX CONCURRENTLY idx_plans_subjects_id ON plans(sys_subjects_id);
CREATE INDEX CONCURRENTLY idx_plans_date_create ON plans(date_create);
CREATE INDEX CONCURRENTLY idx_plans_year ON plans(pln_point_year);

CREATE INDEX CONCURRENTLY idx_rnu_supplier_biin ON rnu(supplier_biin);
CREATE INDEX CONCURRENTLY idx_rnu_dates ON rnu(start_date, end_date);

-- Составные индексы для частых запросов
CREATE INDEX CONCURRENTLY idx_lots_composite ON lots(trdbuy_id, customer_id, last_update_date);
CREATE INDEX CONCURRENTLY idx_contracts_composite ON contracts(customer_id, supplier_id, sign_date);
```

## Оптимизация

### Индексы:

- **B-Tree**: на ID, даты, суммы для range-запросов
- **GIN**: полнотекстовый поиск по названиям
- **Составные**: для многополевых фильтров
- **Частичные**: только для NOT NULL значений

### Партиционирование:

- **По датам**: TrdBuy, Lots, Contracts, Plans партиционированы по годам
- **Автоматическое**: настроить pg_partman для автосоздания партиций

### ETL оптимизация:

- **Batch size**: 1000-5000 записей (учитывая лимит API 200)
- **UPSERT**: `ON CONFLICT (id) DO UPDATE SET ...` для инкрементальной загрузки
- **NULL handling**: все nullable поля для совместимости с API
- **Connections**: connection pooling (pgbouncer) для параллельных загрузок
- **Vacuum**: настроить autovacuum для партиций

### Monitoring:

```sql
-- Статистика по размерам таблиц
SELECT schemaname, tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables WHERE schemaname = 'public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Использование индексов
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes ORDER BY idx_scan DESC;
```
