/**
 * Advanced Search Autocomplete for ZakupAI Web UI
 * Uses Web API endpoints for autocomplete suggestions
 */

class SearchAutocomplete {
    constructor(inputId, suggestionContainerId) {
        this.input = document.getElementById(inputId);
        this.suggestionContainer = document.getElementById(suggestionContainerId);
        this.currentSuggestions = [];
        this.selectedIndex = -1;
        this.debounceTimer = null;

        this.init();
    }

    init() {
        if (!this.input || !this.suggestionContainer) {
            console.error('Autocomplete: Required elements not found');
            return;
        }

        // Event listeners
        this.input.addEventListener('input', (e) => this.onInput(e));
        this.input.addEventListener('keydown', (e) => this.onKeydown(e));
        this.input.addEventListener('blur', () => this.onBlur());
        this.input.addEventListener('focus', (e) => this.onFocus(e));

        // Click outside to close
        document.addEventListener('click', (e) => {
            if (!this.input.contains(e.target) && !this.suggestionContainer.contains(e.target)) {
                this.hideSuggestions();
            }
        });
    }

    onInput(event) {
        const query = event.target.value.trim();

        // Clear previous debounce timer
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }

        // Debounce the API call
        this.debounceTimer = setTimeout(() => {
            if (query.length >= 2) {
                this.fetchSuggestions(query);
            } else {
                this.hideSuggestions();
            }
        }, 300); // 300ms debounce
    }

    onKeydown(event) {
        switch (event.key) {
            case 'ArrowDown':
                event.preventDefault();
                this.selectNext();
                break;
            case 'ArrowUp':
                event.preventDefault();
                this.selectPrevious();
                break;
            case 'Enter':
                event.preventDefault();
                if (this.selectedIndex >= 0) {
                    this.applySuggestion(this.currentSuggestions[this.selectedIndex]);
                }
                break;
            case 'Escape':
                this.hideSuggestions();
                break;
        }
    }

    onBlur() {
        // Delay hiding suggestions to allow click on suggestion
        setTimeout(() => this.hideSuggestions(), 150);
    }

    onFocus(event) {
        const query = event.target.value.trim();
        if (query.length >= 2) {
            this.fetchSuggestions(query);
        }
    }

    async fetchSuggestions(query) {
        try {
            // Show loading indicator
            this.showLoading();

            const response = await fetch(`/api/search/autocomplete?query=${encodeURIComponent(query)}`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            this.currentSuggestions = data.suggestions || [];
            this.selectedIndex = -1;

            if (this.currentSuggestions.length > 0) {
                this.showSuggestions();
            } else {
                this.showNoResults();
            }

        } catch (error) {
            console.error('Autocomplete fetch error:', error);
            this.showError();
        }
    }

    showLoading() {
        this.suggestionContainer.innerHTML = `
            <div class="autocomplete-item loading">
                <i class="bi bi-hourglass-split"></i>
                <span>Поиск...</span>
            </div>
        `;
        this.suggestionContainer.style.display = 'block';
    }

    showError() {
        this.suggestionContainer.innerHTML = `
            <div class="autocomplete-item error">
                <i class="bi bi-exclamation-circle"></i>
                <span>Ошибка загрузки предложений</span>
            </div>
        `;
        this.suggestionContainer.style.display = 'block';
    }

    showNoResults() {
        this.suggestionContainer.innerHTML = `
            <div class="autocomplete-item no-results">
                <i class="bi bi-search"></i>
                <span>Предложений не найдено</span>
            </div>
        `;
        this.suggestionContainer.style.display = 'block';
    }

    showSuggestions() {
        const html = this.currentSuggestions
            .slice(0, 10) // Limit to 10 suggestions
            .map((suggestion, index) => `
                <div class="autocomplete-item ${index === this.selectedIndex ? 'selected' : ''}"
                     data-index="${index}"
                     onclick="searchAutocomplete.applySuggestion('${this.escapeHtml(suggestion)}')">
                    <i class="bi bi-search"></i>
                    <span>${this.highlightQuery(suggestion, this.input.value)}</span>
                </div>
            `).join('');

        this.suggestionContainer.innerHTML = html;
        this.suggestionContainer.style.display = 'block';
    }

    hideSuggestions() {
        this.suggestionContainer.style.display = 'none';
        this.currentSuggestions = [];
        this.selectedIndex = -1;
    }

    selectNext() {
        if (this.currentSuggestions.length === 0) return;

        this.selectedIndex = Math.min(this.selectedIndex + 1, this.currentSuggestions.length - 1);
        this.updateSelection();
    }

    selectPrevious() {
        if (this.currentSuggestions.length === 0) return;

        this.selectedIndex = Math.max(this.selectedIndex - 1, 0);
        this.updateSelection();
    }

    updateSelection() {
        const items = this.suggestionContainer.querySelectorAll('.autocomplete-item');
        items.forEach((item, index) => {
            item.classList.toggle('selected', index === this.selectedIndex);
        });
    }

    applySuggestion(suggestion) {
        this.input.value = suggestion;
        this.hideSuggestions();
        this.input.focus();

        // Trigger input event to update any listeners
        this.input.dispatchEvent(new Event('input', { bubbles: true }));
    }

    highlightQuery(text, query) {
        if (!query) return this.escapeHtml(text);

        const escapedQuery = this.escapeHtml(query);
        const escapedText = this.escapeHtml(text);
        const regex = new RegExp(`(${escapedQuery})`, 'gi');

        return escapedText.replace(regex, '<mark>$1</mark>');
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize autocomplete when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Initialize autocomplete for advanced search input
    window.searchAutocomplete = new SearchAutocomplete('advancedSearchInput', 'searchSuggestions');
});
