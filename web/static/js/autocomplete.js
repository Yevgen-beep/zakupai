/**
 * ZakupAI Autocomplete Component
 * Week 4.1: Enhanced search autocomplete with ChromaDB + SQL fallback
 * Features: Debouncing, Cyrillic support, caching, keyboard navigation
 */

class SearchAutocomplete {
    constructor(inputSelector, suggestionsSelector, options = {}) {
        this.input = document.querySelector(inputSelector);
        this.suggestionsContainer = document.querySelector(suggestionsSelector);

        if (!this.input || !this.suggestionsContainer) {
            console.error('SearchAutocomplete: Required elements not found');
            return;
        }

        // Configuration
        this.config = {
            minLength: 2,
            debounceMs: 300,
            maxSuggestions: 8,
            apiUrl: '/api/search/autocomplete',
            highlightMatches: true,
            ...options
        };

        // State
        this.currentQuery = '';
        this.suggestions = [];
        this.selectedIndex = -1;
        this.isVisible = false;
        this.debounceTimer = null;

        // Bind methods
        this.handleInput = this.handleInput.bind(this);
        this.handleKeyDown = this.handleKeyDown.bind(this);
        this.handleClickOutside = this.handleClickOutside.bind(this);
        this.handleSuggestionClick = this.handleSuggestionClick.bind(this);

        // Initialize
        this.init();
    }

    init() {
        // Setup event listeners
        this.input.addEventListener('input', this.handleInput);
        this.input.addEventListener('keydown', this.handleKeyDown);
        this.input.addEventListener('blur', () => {
            // Delay hiding to allow click events
            setTimeout(() => this.hide(), 150);
        });

        document.addEventListener('click', this.handleClickOutside);

        // Setup suggestions container
        this.suggestionsContainer.className = 'autocomplete-suggestions';
        this.suggestionsContainer.style.display = 'none';

        console.log('SearchAutocomplete initialized');
    }

    handleInput(event) {
        const query = event.target.value.trim();

        if (query === this.currentQuery) {
            return;
        }

        this.currentQuery = query;
        this.selectedIndex = -1;

        // Clear existing timer
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }

        // Debounced search
        this.debounceTimer = setTimeout(() => {
            this.performSearch(query);
        }, this.config.debounceMs);
    }

    async performSearch(query) {
        // Validate query length
        if (query.length < this.config.minLength) {
            this.hide();
            return;
        }

        // Normalize query (remove numbers and special chars, keep Cyrillic and Latin)
        const normalizedQuery = query
            .toLowerCase()
            .replace(/[^\wа-яё\s]/gi, '')
            .trim();

        if (!normalizedQuery) {
            this.hide();
            return;
        }

        try {
            const startTime = Date.now();

            // Show loading state
            this.showLoading();

            // Fetch suggestions
            const response = await fetch(
                `${this.config.apiUrl}?query=${encodeURIComponent(normalizedQuery)}`,
                {
                    method: 'GET',
                    headers: {
                        'Accept': 'application/json',
                        'Content-Type': 'application/json'
                    }
                }
            );

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            const responseTime = Date.now() - startTime;

            // Log performance
            console.log(`Autocomplete query: "${query}" -> ${data.suggestions?.length || 0} results in ${responseTime}ms`);

            // Update suggestions
            this.updateSuggestions(data.suggestions || [], query);

        } catch (error) {
            console.error('Autocomplete search failed:', error);
            this.showError('Ошибка поиска');
        }
    }

    showLoading() {
        this.suggestionsContainer.innerHTML = `
            <div class="autocomplete-loading">
                <span class="loading-spinner"></span>
                Поиск...
            </div>
        `;
        this.show();
    }

    showError(message) {
        this.suggestionsContainer.innerHTML = `
            <div class="autocomplete-error">
                <span class="error-icon">⚠</span>
                ${message}
            </div>
        `;
        this.show();
    }

    updateSuggestions(suggestions, originalQuery) {
        this.suggestions = suggestions.slice(0, this.config.maxSuggestions);

        if (this.suggestions.length === 0) {
            this.hide();
            return;
        }

        // Build suggestions HTML
        const suggestionsHtml = this.suggestions
            .map((suggestion, index) => {
                const highlighted = this.config.highlightMatches
                    ? this.highlightText(suggestion, originalQuery)
                    : suggestion;

                return `
                    <div class="autocomplete-item" data-index="${index}">
                        <span class="suggestion-text">${highlighted}</span>
                        <span class="suggestion-icon">🔍</span>
                    </div>
                `;
            })
            .join('');

        this.suggestionsContainer.innerHTML = suggestionsHtml;

        // Add click listeners
        this.suggestionsContainer.querySelectorAll('.autocomplete-item').forEach((item, index) => {
            item.addEventListener('click', () => this.selectSuggestion(index));
            item.addEventListener('mouseenter', () => this.highlightItem(index));
        });

        this.show();
    }

    highlightText(text, query) {
        if (!query || query.length < 2) {
            return text;
        }

        // Case-insensitive highlighting
        const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
        return text.replace(regex, '<mark>$1</mark>');
    }

    handleKeyDown(event) {
        if (!this.isVisible || this.suggestions.length === 0) {
            return;
        }

        switch (event.key) {
            case 'ArrowDown':
                event.preventDefault();
                this.selectedIndex = Math.min(this.selectedIndex + 1, this.suggestions.length - 1);
                this.highlightItem(this.selectedIndex);
                break;

            case 'ArrowUp':
                event.preventDefault();
                this.selectedIndex = Math.max(this.selectedIndex - 1, -1);
                this.highlightItem(this.selectedIndex);
                break;

            case 'Enter':
                event.preventDefault();
                if (this.selectedIndex >= 0) {
                    this.selectSuggestion(this.selectedIndex);
                }
                break;

            case 'Escape':
                this.hide();
                this.input.blur();
                break;

            case 'Tab':
                // Allow tab to navigate away
                this.hide();
                break;
        }
    }

    handleClickOutside(event) {
        if (!this.input.contains(event.target) && !this.suggestionsContainer.contains(event.target)) {
            this.hide();
        }
    }

    handleSuggestionClick(event) {
        const item = event.target.closest('.autocomplete-item');
        if (item) {
            const index = parseInt(item.dataset.index);
            this.selectSuggestion(index);
        }
    }

    selectSuggestion(index) {
        if (index >= 0 && index < this.suggestions.length) {
            const selectedText = this.suggestions[index];
            this.input.value = selectedText;
            this.currentQuery = selectedText;
            this.hide();

            // Trigger input event to notify parent components
            this.input.dispatchEvent(new Event('input', { bubbles: true }));

            // Custom event for selection
            this.input.dispatchEvent(new CustomEvent('autocomplete:select', {
                detail: {
                    value: selectedText,
                    index: index
                }
            }));

            // Focus back on input
            this.input.focus();
        }
    }

    highlightItem(index) {
        // Remove previous highlights
        this.suggestionsContainer.querySelectorAll('.autocomplete-item').forEach(item => {
            item.classList.remove('highlighted');
        });

        // Highlight current item
        if (index >= 0 && index < this.suggestions.length) {
            const item = this.suggestionsContainer.querySelector(`[data-index="${index}"]`);
            if (item) {
                item.classList.add('highlighted');
            }
        }

        this.selectedIndex = index;
    }

    show() {
        if (!this.isVisible) {
            this.suggestionsContainer.style.display = 'block';
            this.isVisible = true;
        }
    }

    hide() {
        if (this.isVisible) {
            this.suggestionsContainer.style.display = 'none';
            this.isVisible = false;
            this.selectedIndex = -1;
        }
    }

    // Public methods
    clear() {
        this.input.value = '';
        this.currentQuery = '';
        this.hide();
    }

    setValue(value) {
        this.input.value = value;
        this.currentQuery = value;
        this.hide();
    }

    destroy() {
        // Clean up event listeners
        this.input.removeEventListener('input', this.handleInput);
        this.input.removeEventListener('keydown', this.handleKeyDown);
        document.removeEventListener('click', this.handleClickOutside);

        // Clear timers
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }

        // Hide suggestions
        this.hide();

        console.log('SearchAutocomplete destroyed');
    }
}

// Utility function for debouncing (exported for external use)
function debounce(func, delay) {
    let timeoutId;
    return function (...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => func.apply(this, args), delay);
    };
}

// Export debounce utility
if (typeof window !== 'undefined') {
    window.debounce = debounce;
}

// Auto-initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    // Look for elements with data-autocomplete attribute
    const autoElements = document.querySelectorAll('[data-autocomplete]');

    autoElements.forEach(input => {
        const suggestionsId = input.dataset.autocomplete;
        const suggestionsContainer = document.getElementById(suggestionsId);

        if (suggestionsContainer) {
            new SearchAutocomplete(`#${input.id}`, `#${suggestionsId}`, {
                minLength: parseInt(input.dataset.minLength) || 2,
                maxSuggestions: parseInt(input.dataset.maxSuggestions) || 8
            });
        }
    });

    console.log('Auto-initialized autocomplete for', autoElements.length, 'elements');
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SearchAutocomplete;
} else if (typeof window !== 'undefined') {
    window.SearchAutocomplete = SearchAutocomplete;
}
