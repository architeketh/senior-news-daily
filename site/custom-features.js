/**
 * Senior News Daily - Custom Features Module
 * Adds ability to manage custom feeds and delete articles
 */

class SeniorNewsCustomizer {
    constructor() {
        this.customFeeds = this.loadCustomFeeds();
        this.deletedArticles = this.loadDeletedArticles();
        this.init();
    }

    init() {
        this.setupUI();
        this.applyArticleFilters();
        this.updateStats();
    }

    // ============== CUSTOM FEEDS MANAGEMENT ==============
    
    loadCustomFeeds() {
        try {
            return JSON.parse(localStorage.getItem('snd_customFeeds')) || [];
        } catch (e) {
            console.error('Error loading custom feeds:', e);
            return [];
        }
    }

    saveCustomFeeds() {
        localStorage.setItem('snd_customFeeds', JSON.stringify(this.customFeeds));
        this.updateStats();
    }

    addCustomFeed(feedData) {
        const feed = {
            id: Date.now(),
            name: feedData.name,
            url: feedData.url,
            category: feedData.category || 'General',
            dateAdded: new Date().toISOString(),
            enabled: true
        };

        this.customFeeds.push(feed);
        this.saveCustomFeeds();
        return feed;
    }

    removeCustomFeed(feedId) {
        this.customFeeds = this.customFeeds.filter(f => f.id !== feedId);
        this.saveCustomFeeds();
    }

    toggleCustomFeed(feedId) {
        const feed = this.customFeeds.find(f => f.id === feedId);
        if (feed) {
            feed.enabled = !feed.enabled;
            this.saveCustomFeeds();
        }
    }

    // ============== ARTICLE DELETION ==============
    
    loadDeletedArticles() {
        try {
            return JSON.parse(localStorage.getItem('snd_deletedArticles')) || [];
        } catch (e) {
            console.error('Error loading deleted articles:', e);
            return [];
        }
    }

    saveDeletedArticles() {
        localStorage.setItem('snd_deletedArticles', JSON.stringify(this.deletedArticles));
        this.updateStats();
    }

    deleteArticle(articleUrl) {
        if (!this.deletedArticles.includes(articleUrl)) {
            this.deletedArticles.push(articleUrl);
            this.saveDeletedArticles();
        }
    }

    restoreArticle(articleUrl) {
        this.deletedArticles = this.deletedArticles.filter(url => url !== articleUrl);
        this.saveDeletedArticles();
    }

    isArticleDeleted(articleUrl) {
        return this.deletedArticles.includes(articleUrl);
    }

    // ============== UI SETUP ==============
    
    setupUI() {
        this.injectStyles();
        this.addControlButtons();
        this.addDeleteButtonsToArticles();
    }

    injectStyles() {
        const styles = `
            <style>
                .snd-controls {
                    background: #f8f9fa;
                    padding: 15px 20px;
                    border-bottom: 2px solid #dee2e6;
                    display: flex;
                    gap: 10px;
                    flex-wrap: wrap;
                    align-items: center;
                }

                .snd-btn {
                    padding: 8px 16px;
                    border: none;
                    border-radius: 5px;
                    cursor: pointer;
                    font-size: 14px;
                    font-weight: 600;
                    transition: all 0.3s ease;
                }

                .snd-btn-primary {
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                }

                .snd-btn-primary:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
                }

                .snd-btn-secondary {
                    background: #6c757d;
                    color: white;
                }

                .snd-btn-secondary:hover {
                    background: #5a6268;
                }

                .snd-btn-danger {
                    background: #dc3545;
                    color: white;
                    padding: 5px 12px;
                    font-size: 12px;
                }

                .snd-btn-danger:hover {
                    background: #c82333;
                }

                .snd-btn-success {
                    background: #28a745;
                    color: white;
                    padding: 5px 12px;
                    font-size: 12px;
                }

                .snd-btn-success:hover {
                    background: #218838;
                }

                .snd-modal {
                    display: none;
                    position: fixed;
                    z-index: 10000;
                    left: 0;
                    top: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0,0,0,0.5);
                    animation: fadeIn 0.3s ease;
                }

                @keyframes fadeIn {
                    from { opacity: 0; }
                    to { opacity: 1; }
                }

                .snd-modal-content {
                    background: white;
                    margin: 5% auto;
                    padding: 30px;
                    border-radius: 10px;
                    width: 90%;
                    max-width: 600px;
                    max-height: 80vh;
                    overflow-y: auto;
                    box-shadow: 0 10px 40px rgba(0,0,0,0.3);
                    animation: slideDown 0.3s ease;
                }

                @keyframes slideDown {
                    from {
                        transform: translateY(-50px);
                        opacity: 0;
                    }
                    to {
                        transform: translateY(0);
                        opacity: 1;
                    }
                }

                .snd-modal-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 20px;
                    padding-bottom: 15px;
                    border-bottom: 2px solid #dee2e6;
                }

                .snd-modal-header h2 {
                    margin: 0;
                    color: #667eea;
                }

                .snd-close-btn {
                    background: none;
                    border: none;
                    font-size: 28px;
                    color: #aaa;
                    cursor: pointer;
                    line-height: 1;
                }

                .snd-close-btn:hover {
                    color: #000;
                }

                .snd-form-group {
                    margin-bottom: 15px;
                }

                .snd-form-group label {
                    display: block;
                    margin-bottom: 5px;
                    font-weight: 600;
                    color: #495057;
                }

                .snd-form-group input {
                    width: 100%;
                    padding: 10px;
                    border: 2px solid #dee2e6;
                    border-radius: 5px;
                    font-size: 14px;
                }

                .snd-form-group input:focus {
                    outline: none;
                    border-color: #667eea;
                }

                .snd-modal-actions {
                    display: flex;
                    gap: 10px;
                    justify-content: flex-end;
                    margin-top: 20px;
                }

                .snd-feed-item {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 15px;
                    background: #f8f9fa;
                    border-radius: 8px;
                    margin-bottom: 10px;
                    border-left: 4px solid #667eea;
                }

                .snd-feed-info {
                    flex: 1;
                }

                .snd-feed-name {
                    font-weight: 600;
                    color: #333;
                    margin-bottom: 5px;
                }

                .snd-feed-url {
                    font-size: 0.85em;
                    color: #6c757d;
                    word-break: break-all;
                }

                .snd-feed-category {
                    display: inline-block;
                    background: #667eea;
                    color: white;
                    padding: 2px 8px;
                    border-radius: 12px;
                    font-size: 0.75em;
                    margin-top: 5px;
                }

                .snd-feed-actions {
                    display: flex;
                    gap: 5px;
                }

                .snd-article-deleted {
                    opacity: 0.5;
                    background: #f8d7da;
                }

                .snd-stats-badge {
                    background: #667eea;
                    color: white;
                    padding: 4px 12px;
                    border-radius: 15px;
                    font-size: 13px;
                    font-weight: 600;
                }

                .snd-empty-state {
                    text-align: center;
                    padding: 40px 20px;
                    color: #6c757d;
                }

                .snd-alert {
                    padding: 15px;
                    margin: 15px 0;
                    border-radius: 5px;
                    background: #d1ecf1;
                    color: #0c5460;
                    border: 1px solid #bee5eb;
                }

                .snd-alert-warning {
                    background: #fff3cd;
                    color: #856404;
                    border-color: #ffeaa7;
                }

                .snd-article-actions {
                    display: flex;
                    gap: 8px;
                    margin-top: 10px;
                }

                @media (max-width: 768px) {
                    .snd-controls {
                        flex-direction: column;
                        align-items: stretch;
                    }

                    .snd-btn {
                        width: 100%;
                    }

                    .snd-modal-content {
                        width: 95%;
                        margin: 10% auto;
                    }
                }
            </style>
        `;
        document.head.insertAdjacentHTML('beforeend', styles);
    }

    addControlButtons() {
        const mainContent = document.querySelector('body > *') || document.body;
        
        const controlsHTML = `
            <div class="snd-controls">
                <button class="snd-btn snd-btn-primary" onclick="sndCustomizer.openAddFeedModal()">
                    ➕ Add News Source
                </button>
                <button class="snd-btn snd-btn-secondary" onclick="sndCustomizer.openManageFeedsModal()">
                    🔧 Manage Sources (<span id="snd-custom-count">${this.customFeeds.length}</span>)
                </button>
                <button class="snd-btn snd-btn-secondary" onclick="sndCustomizer.openDeletedArticlesModal()">
                    🗑️ Deleted Articles (<span id="snd-deleted-count">${this.deletedArticles.length}</span>)
                </button>
                <div style="margin-left: auto;">
                    <span class="snd-stats-badge">
                        ${this.customFeeds.filter(f => f.enabled).length} Custom Feeds Active
                    </span>
                </div>
            </div>
        `;

        mainContent.insertAdjacentHTML('afterbegin', controlsHTML);
        this.addModals();
    }

    addDeleteButtonsToArticles() {
        const articles = document.querySelectorAll('a[href^="http"]');
        
        articles.forEach(link => {
            const articleUrl = link.href;
            const parentLi = link.closest('li');
            
            if (!parentLi || parentLi.querySelector('.snd-article-actions')) return;
            
            const isDeleted = this.isArticleDeleted(articleUrl);
            
            if (isDeleted) {
                parentLi.classList.add('snd-article-deleted');
            }
            
            const actionsHTML = `
                <div class="snd-article-actions">
                    ${isDeleted ? 
                        `<button class="snd-btn snd-btn-success" onclick="sndCustomizer.restoreArticleUI('${articleUrl}')">↶ Restore</button>` :
                        `<button class="snd-btn snd-btn-danger" onclick="sndCustomizer.deleteArticleUI('${articleUrl}')">🗑️ Remove</button>`
                    }
                </div>
            `;
            
            parentLi.insertAdjacentHTML('beforeend', actionsHTML);
        });
    }

    addModals() {
        const modalsHTML = `
            <!-- Add Feed Modal -->
            <div id="snd-add-feed-modal" class="snd-modal">
                <div class="snd-modal-content">
                    <div class="snd-modal-header">
                        <h2>Add Custom News Source</h2>
                        <button class="snd-close-btn" onclick="sndCustomizer.closeModal('snd-add-feed-modal')">&times;</button>
                    </div>
                    <div class="snd-alert snd-alert-warning">
                        <strong>Note:</strong> Custom feeds are stored locally in your browser. The site will continue to show default feeds plus any custom ones you add.
                    </div>
                    <form id="snd-add-feed-form">
                        <div class="snd-form-group">
                            <label>Source Name *</label>
                            <input type="text" id="snd-feed-name" placeholder="e.g., Senior Living Magazine" required>
                        </div>
                        <div class="snd-form-group">
                            <label>RSS Feed URL *</label>
                            <input type="url" id="snd-feed-url" placeholder="https://example.com/rss" required>
                        </div>
                        <div class="snd-form-group">
                            <label>Category</label>
                            <input type="text" id="snd-feed-category" placeholder="e.g., Lifestyle, Health, Travel">
                        </div>
                        <div class="snd-modal-actions">
                            <button type="button" class="snd-btn snd-btn-secondary" onclick="sndCustomizer.closeModal('snd-add-feed-modal')">Cancel</button>
                            <button type="submit" class="snd-btn snd-btn-primary">Add Source</button>
                        </div>
                    </form>
                </div>
            </div>

            <!-- Manage Feeds Modal -->
            <div id="snd-manage-feeds-modal" class="snd-modal">
                <div class="snd-modal-content">
                    <div class="snd-modal-header">
                        <h2>Manage Custom Sources</h2>
                        <button class="snd-close-btn" onclick="sndCustomizer.closeModal('snd-manage-feeds-modal')">&times;</button>
                    </div>
                    <div id="snd-feeds-list"></div>
                    <div class="snd-modal-actions">
                        <button class="snd-btn snd-btn-secondary" onclick="sndCustomizer.closeModal('snd-manage-feeds-modal')">Close</button>
                    </div>
                </div>
            </div>

            <!-- Deleted Articles Modal -->
            <div id="snd-deleted-articles-modal" class="snd-modal">
                <div class="snd-modal-content">
                    <div class="snd-modal-header">
                        <h2>Deleted Articles</h2>
                        <button class="snd-close-btn" onclick="sndCustomizer.closeModal('snd-deleted-articles-modal')">&times;</button>
                    </div>
                    <div id="snd-deleted-list"></div>
                    <div class="snd-modal-actions">
                        <button class="snd-btn snd-btn-danger" onclick="sndCustomizer.clearAllDeleted()">Clear All</button>
                        <button class="snd-btn snd-btn-secondary" onclick="sndCustomizer.closeModal('snd-deleted-articles-modal')">Close</button>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalsHTML);

        // Setup form submission
        document.getElementById('snd-add-feed-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleAddFeed();
        });

        // Close modals when clicking outside
        document.querySelectorAll('.snd-modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.closeModal(modal.id);
                }
            });
        });
    }

    // ============== UI INTERACTIONS ==============

    openAddFeedModal() {
        document.getElementById('snd-add-feed-modal').style.display = 'block';
    }

    openManageFeedsModal() {
        const listEl = document.getElementById('snd-feeds-list');
        
        if (this.customFeeds.length === 0) {
            listEl.innerHTML = '<div class="snd-empty-state">No custom sources added yet. Click "Add News Source" to get started!</div>';
        } else {
            listEl.innerHTML = this.customFeeds.map(feed => `
                <div class="snd-feed-item">
                    <div class="snd-feed-info">
                        <div class="snd-feed-name">${this.escapeHtml(feed.name)}</div>
                        <div class="snd-feed-url">${this.escapeHtml(feed.url)}</div>
                        <span class="snd-feed-category">${this.escapeHtml(feed.category)}</span>
                    </div>
                    <div class="snd-feed-actions">
                        <button class="snd-btn snd-btn-danger" onclick="sndCustomizer.removeFeedUI(${feed.id})">Remove</button>
                    </div>
                </div>
            `).join('');
        }
        
        document.getElementById('snd-manage-feeds-modal').style.display = 'block';
    }

    openDeletedArticlesModal() {
        const listEl = document.getElementById('snd-deleted-list');
        
        if (this.deletedArticles.length === 0) {
            listEl.innerHTML = '<div class="snd-empty-state">No deleted articles.</div>';
        } else {
            listEl.innerHTML = this.deletedArticles.map(url => `
                <div class="snd-feed-item">
                    <div class="snd-feed-info">
                        <div class="snd-feed-url">${this.escapeHtml(url)}</div>
                    </div>
                    <div class="snd-feed-actions">
                        <button class="snd-btn snd-btn-success" onclick="sndCustomizer.restoreArticleUI('${url}')">Restore</button>
                    </div>
                </div>
            `).join('');
        }
        
        document.getElementById('snd-deleted-articles-modal').style.display = 'block';
    }

    closeModal(modalId) {
        document.getElementById(modalId).style.display = 'none';
    }

    handleAddFeed() {
        const name = document.getElementById('snd-feed-name').value.trim();
        const url = document.getElementById('snd-feed-url').value.trim();
        const category = document.getElementById('snd-feed-category').value.trim();

        if (!name || !url) {
            alert('Please fill in all required fields.');
            return;
        }

        try {
            new URL(url);
        } catch (e) {
            alert('Please enter a valid URL.');
            return;
        }

        this.addCustomFeed({ name, url, category });
        
        alert(`✅ Successfully added "${name}"!\n\nYour custom feed has been saved. Note: Articles from this feed will appear on the next site update.`);
        
        this.closeModal('snd-add-feed-modal');
        document.getElementById('snd-add-feed-form').reset();
        this.updateStats();
    }

    removeFeedUI(feedId) {
        if (confirm('Are you sure you want to remove this custom feed?')) {
            this.removeCustomFeed(feedId);
            this.openManageFeedsModal(); // Refresh the list
        }
    }

    deleteArticleUI(articleUrl) {
        this.deleteArticle(articleUrl);
        const links = document.querySelectorAll(`a[href="${articleUrl}"]`);
        links.forEach(link => {
            const parentLi = link.closest('li');
            if (parentLi) {
                parentLi.style.transition = 'all 0.3s ease';
                parentLi.style.opacity = '0.5';
                parentLi.style.background = '#f8d7da';
                parentLi.classList.add('snd-article-deleted');
                
                const actions = parentLi.querySelector('.snd-article-actions');
                if (actions) {
                    actions.innerHTML = `<button class="snd-btn snd-btn-success" onclick="sndCustomizer.restoreArticleUI('${articleUrl}')">↶ Restore</button>`;
                }
            }
        });
    }

    restoreArticleUI(articleUrl) {
        this.restoreArticle(articleUrl);
        const links = document.querySelectorAll(`a[href="${articleUrl}"]`);
        links.forEach(link => {
            const parentLi = link.closest('li');
            if (parentLi) {
                parentLi.style.opacity = '1';
                parentLi.style.background = '';
                parentLi.classList.remove('snd-article-deleted');
                
                const actions = parentLi.querySelector('.snd-article-actions');
                if (actions) {
                    actions.innerHTML = `<button class="snd-btn snd-btn-danger" onclick="sndCustomizer.deleteArticleUI('${articleUrl}')">🗑️ Remove</button>`;
                }
            }
        });
        this.closeModal('snd-deleted-articles-modal');
    }

    clearAllDeleted() {
        if (confirm('Are you sure you want to restore all deleted articles?')) {
            this.deletedArticles = [];
            this.saveDeletedArticles();
            location.reload();
        }
    }

    applyArticleFilters() {
        // Hide deleted articles on page load
        this.deletedArticles.forEach(url => {
            const links = document.querySelectorAll(`a[href="${url}"]`);
            links.forEach(link => {
                const parentLi = link.closest('li');
                if (parentLi) {
                    parentLi.classList.add('snd-article-deleted');
                    parentLi.style.opacity = '0.5';
                    parentLi.style.background = '#f8d7da';
                }
            });
        });
    }

    updateStats() {
        const customCountEl = document.getElementById('snd-custom-count');
        const deletedCountEl = document.getElementById('snd-deleted-count');
        
        if (customCountEl) customCountEl.textContent = this.customFeeds.length;
        if (deletedCountEl) deletedCountEl.textContent = this.deletedArticles.length;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ============== EXPORT FEEDS FOR YAML ==============
    
    exportCustomFeedsForYAML() {
        if (this.customFeeds.length === 0) {
            alert('No custom feeds to export.');
            return;
        }

        const yamlLines = [
            '# Custom feeds added by user',
            ...this.customFeeds.map(feed => `  - ${feed.url}  # ${feed.name} (${feed.category})`)
        ];

        const yamlContent = yamlLines.join('\n');
        
        // Copy to clipboard
        navigator.clipboard.writeText(yamlContent).then(() => {
            alert('✅ Custom feeds copied to clipboard!\n\nYou can paste these into your feeds.yaml file.');
        }).catch(() => {
            // Fallback: show in modal
            alert('Custom feeds:\n\n' + yamlContent);
        });

        console.log('Custom Feeds for feeds.yaml:\n', yamlContent);
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.sndCustomizer = new SeniorNewsCustomizer();
    });
} else {
    window.sndCustomizer = new SeniorNewsCustomizer();
}
