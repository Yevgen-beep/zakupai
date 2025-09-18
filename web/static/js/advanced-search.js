/**
 * Advanced Search Form Handler for ZakupAI Web UI
 */

class AdvancedSearchHandler {
    constructor() {
        this.form = document.getElementById('advancedSearchForm');
        this.searchInput = document.getElementById('advancedSearchInput');
        this.minAmountInput = document.getElementById('minAmount');
        this.maxAmountInput = document.getElementById('maxAmount');
        this.statusInput = document.getElementById('statusFilter');
        this.limitInput = document.getElementById('limitResults');
        this.loadingDiv = document.getElementById('searchLoading');
        this.resultsDiv = document.getElementById('searchResults');
        this.resultsContent = document.getElementById('searchResultsContent');

        this.init();
    }

    init() {
        if (!this.form) {
            console.error('Advanced search form not found');
            return;
        }

        // Event listeners
        this.form.addEventListener('submit', (e) => this.handleSubmit(e));

        // Amount validation
        this.minAmountInput.addEventListener('change', () => this.validateAmountRange());
        this.maxAmountInput.addEventListener('change', () => this.validateAmountRange());
    }

    validateAmountRange() {
        const minAmount = parseFloat(this.minAmountInput.value) || 0;
        const maxAmount = parseFloat(this.maxAmountInput.value) || 0;

        if (minAmount > 0 && maxAmount > 0 && minAmount > maxAmount) {
            this.maxAmountInput.setCustomValidity('Максимальная сумма должна быть больше минимальной');
        } else {
            this.maxAmountInput.setCustomValidity('');
        }
    }

    async handleSubmit(event) {
        event.preventDefault();

        const query = this.searchInput.value.trim();
        if (query.length < 2) {
            this.showError('Поисковый запрос должен содержать минимум 2 символа');
            return;
        }

        // Validate amount range
        this.validateAmountRange();
        if (!this.form.checkValidity()) {
            this.form.reportValidity();
            return;
        }

        // Prepare search parameters
        const searchParams = {
            query: query,
            limit: parseInt(this.limitInput.value) || 10,
            offset: 0
        };

        // Add optional filters
        const minAmount = parseFloat(this.minAmountInput.value);
        const maxAmount = parseFloat(this.maxAmountInput.value);
        const status = this.statusInput.value;

        if (!isNaN(minAmount) && minAmount > 0) {
            searchParams.min_amount = minAmount;
        }
        if (!isNaN(maxAmount) && maxAmount > 0) {
            searchParams.max_amount = maxAmount;
        }
        if (status) {
            searchParams.status = status;
        }

        await this.performSearch(searchParams);
    }

    async performSearch(params) {
        try {
            this.showLoading();

            const response = await fetch('/api/search/advanced', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(params)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            this.showResults(data, params);

        } catch (error) {
            console.error('Search error:', error);
            this.showError(`Ошибка поиска: ${error.message}`);
        } finally {
            this.hideLoading();
        }
    }

    showLoading() {
        this.loadingDiv.style.display = 'block';
        this.resultsDiv.style.display = 'none';
    }

    hideLoading() {
        this.loadingDiv.style.display = 'none';
    }

    showError(message) {
        this.hideLoading();
        this.resultsContent.innerHTML = `
            <div class="alert alert-danger" role="alert">
                <i class="bi bi-exclamation-triangle"></i>
                ${this.escapeHtml(message)}
            </div>
        `;
        this.resultsDiv.style.display = 'block';
    }

    showResults(data, searchParams) {
        const { results, total_count } = data;

        if (!results || results.length === 0) {
            this.resultsContent.innerHTML = `
                <div class="alert alert-info" role="alert">
                    <i class="bi bi-info-circle"></i>
                    По вашему запросу ничего не найдено. Попробуйте изменить параметры поиска.
                </div>
            `;
        } else {
            // Create filter summary
            const filters = [];
            if (searchParams.min_amount) filters.push(`от ${searchParams.min_amount.toLocaleString()} тенге`);
            if (searchParams.max_amount) filters.push(`до ${searchParams.max_amount.toLocaleString()} тенге`);
            if (searchParams.status) filters.push(`статус ${searchParams.status}`);

            const filterSummary = filters.length > 0 ? ` (${filters.join(', ')})` : '';

            let html = `
                <div class="search-summary mb-3">
                    <h6>
                        Найдено ${total_count} лот(ов) по запросу:
                        <strong>"${this.escapeHtml(searchParams.query)}"</strong>${filterSummary}
                    </h6>
                    <small class="text-muted">Показано ${results.length} из ${total_count} результатов</small>
                </div>
            `;

            // Render results
            html += results.map(lot => this.renderLotResult(lot)).join('');

            // Pagination info
            if (total_count > results.length) {
                html += `
                    <div class="pagination-info mt-3 text-center">
                        <p class="text-muted">
                            Показаны первые ${results.length} результатов из ${total_count}
                        </p>
                    </div>
                `;
            }

            this.resultsContent.innerHTML = html;
        }

        this.resultsDiv.style.display = 'block';
    }

    renderLotResult(lot) {
        const customerInfo = lot.customerNameRu ?
            `<div class="search-result-meta">
                <i class="bi bi-building"></i>
                Заказчик: ${this.escapeHtml(lot.customerNameRu)}
            </div>` : '';

        return `
            <div class="search-result-item">
                <a href="/lot/${lot.id}" class="search-result-title">
                    ${this.escapeHtml(lot.nameRu || 'Название не указано')}
                </a>
                ${customerInfo}
                <div class="search-result-meta">
                    <span class="search-result-amount">
                        <i class="bi bi-currency-exchange"></i>
                        ${this.formatAmount(lot.amount)} тенге
                    </span>
                    <span class="search-result-status status-${lot.status} ms-2">
                        Статус ${lot.status}
                    </span>
                </div>
                <div class="search-result-meta">
                    <i class="bi bi-hash"></i>
                    ID лота: ${lot.id} | ID тендера: ${lot.trdBuyId}
                </div>
            </div>
        `;
    }

    formatAmount(amount) {
        if (amount === null || amount === undefined) return '0';
        return parseFloat(amount).toLocaleString('ru-KZ');
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    window.advancedSearchHandler = new AdvancedSearchHandler();
});

// Existing lot search functionality (preserve existing functionality)
document.getElementById('lotSearchForm')?.addEventListener('submit', function(e) {
    e.preventDefault();
    const lotInput = document.getElementById('lotInput').value.trim();

    if (!lotInput) {
        alert('Пожалуйста, введите ID лота или URL');
        return;
    }

    // Extract lot ID from URL or use as is
    let lotId = lotInput;
    const urlMatch = lotInput.match(/lot[/-](\d+)/i);
    if (urlMatch) {
        lotId = urlMatch[1];
    }

    if (!/^\d+$/.test(lotId)) {
        alert('Некорректный ID лота. Должен содержать только цифры.');
        return;
    }

    // Navigate to lot page
    window.location.href = `/lot/${lotId}`;
});
