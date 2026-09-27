import { el } from '../dom.js';
import { html, render } from '../html.js';
import { t } from '../i18n.js';
import { ask } from '../mirror.js';

const COLUMNS = ['state', 'role', 'service', 'image', 'version', 'latest', 'pull'];
const RANK = { behind: 0, unknown: 1, floating: 2, current: 3 };

function Table({ view }) {
  const rows = view.rows();
  const row = entry => {
    const pull = view.pullFor(entry);
    return html`
      <tr>
        <td class=${`feed-mark update-${entry.state}`}>${t(`updates.state.${entry.state}`)}</td>
        <td data-role-name=${entry.role}>${view.roleInfo.labelNode(entry.role)}</td>
        <td>${entry.service}</td>
        <td class="update-image">${entry.image}</td>
        <td class="update-version">${entry.version}</td>
        <td class="update-version">${entry.latest}</td>
        <td>
          ${pull
            ? html`<a href=${pull.html_url} target="_blank" rel="noreferrer">${`#${pull.number}`}</a>`
            : ''}
        </td>
      </tr>
    `;
  };
  return html`
    <h2>${t('view.itemsWith', { view: t('view.updates') })}</h2>
    <div class="feed-filters">
      <input type="search" class="form-control form-control-sm feed-search" value=${view.filters.search}
             placeholder=${t('feed.filter.search')} aria-label=${t('feed.filter.search')}
             onInput=${event => view.setFilter('search', event.currentTarget.value)} />
      ${[['state', 'updates.column.state'], ['role', 'updates.column.role']].map(([name, label]) => html`
        <label class="feed-filter">
          <span>${t(label)}</span>
          <select class="form-select form-select-sm" data-filter=${name}
                  onChange=${event => view.setFilter(name, event.currentTarget.value)}>
            <option value="">${t('feed.filter.all')}</option>
            ${view.options(name).map(([value, count]) => html`
              <option value=${value} selected=${view.filters[name] === value}>
                ${`${name === 'state' ? t(`updates.state.${value}`) : value} (${count})`}
              </option>
            `)}
          </select>
        </label>
      `)}
      <button type="button" class="btn btn-sm btn-outline-secondary update-again"
              onClick=${() => view.show(true)}>${t('loader.task.retry')}</button>
    </div>
    <p class="table-note">${view.note}</p>
    <div class="table-scroll">
      ${view.items && html`
        <table class="table table-sm feed-table update-table">
          <thead><tr>${COLUMNS.map(column => html`<th>${t(`updates.column.${column}`)}</th>`)}</tr></thead>
          <tbody>${rows.map(row)}</tbody>
        </table>
      `}
    </div>
  `;
}

export class UpdatesView {
  // Args:
  //   api: the GitHubApi, for the open pull requests an update may already have.
  //   range: the GitRange, whose catalog names the repository they belong to.
  //   roleInfo: for the role label, so a role reads as it does everywhere else.
  constructor(api, range, roleInfo, container) {
    this.api = api;
    this.range = range;
    this.roleInfo = roleInfo;
    this.container = container;
    this.root = el('div', { className: 'table-section' });
    this.items = null;
    this.pulls = [];
    this.note = '';
    this.loaded = null;
    this.onFilter = null;
    /** @type {(promise: Promise<unknown>, label: () => string) => unknown} */
    this.track = promise => promise;
    this.filters = { search: '', state: '', role: '' };
  }

  setFilter(name, value) {
    this.filters[name] = value || '';
    this._render();
    if (this.onFilter) this.onFilter();
  }

  // Returns: the open pull request that names this image, or null. A bump is
  //   titled after the image, so the image name is what connects the two.
  pullFor(entry) {
    const name = entry.image.split('/').pop().toLowerCase();
    return this.pulls.find(pull => String(pull.title || '').toLowerCase().includes(name)) || null;
  }

  // Returns: the rows the filters keep, worst first.
  rows() {
    const search = this.filters.search.trim().toLowerCase();
    return (this.items || []).filter(entry => (!this.filters.state || entry.state === this.filters.state)
      && (!this.filters.role || entry.role === this.filters.role)
      && (!search || `${entry.role} ${entry.service} ${entry.image} ${entry.version}`
        .toLowerCase().includes(search)))
      .sort((one, other) => RANK[one.state] - RANK[other.state]
        || one.role.localeCompare(other.role)
        || one.service.localeCompare(other.service));
  }

  // Returns: [[value, count]] for one filter, the states worst first and the
  //   roles by how much each has to answer for.
  options(name) {
    const counts = new Map();
    for (const entry of this.items || []) {
      const value = entry[name];
      counts.set(value, (counts.get(value) || 0) + 1);
    }
    return [...counts].sort((one, other) => (name === 'state'
      ? RANK[one[0]] - RANK[other[0]]
      : other[1] - one[1] || String(one[0]).localeCompare(other[0])));
  }

  invalidate() {
    this.items = null;
    this.loaded = null;
  }

  refresh() {
    if (this.items) this._render();
  }

  // Args:
  //   fresh: true asks the registries again rather than the kept answer.
  show(fresh = false) {
    this.container.replaceChildren(this.root);
    if (this.loaded && !fresh) {
      this._render();
      return this.loaded;
    }
    this.note = t('updates.reading');
    this.items = null;
    this._paint();
    this.loaded = this.track(
      Promise.all([
        ask(`/git/updates${fresh ? '?fresh=true' : ''}`),
        this._pulls(),
      ]).then(([body]) => {
        this.items = body.items || [];
        this.at = body.at || 0;
        this._render();
        return this.items;
      }).catch(error => {
        this.note = t('updates.failed', { message: error.message });
        this._paint();
        return [];
      }),
      () => t('updates.reading')
    );
    return this.loaded;
  }

  _pulls() {
    const root = this.range.catalog ? this.range.catalog.root : '';
    if (!root) return Promise.resolve([]);
    return this.api.get(`/repos/${root}/pulls?state=open&per_page=100`, false)
      .then(listed => {
        this.pulls = Array.isArray(listed) ? listed : [];
        return this.pulls;
      })
      .catch(() => []);
  }

  _render() {
    const all = this.items || [];
    const rows = this.rows();
    const behind = all.filter(entry => entry.state === 'behind');
    this.note = [
      t('updates.note', { n: behind.length, total: all.length }),
      t('updates.asked', { date: new Date((this.at || 0) * 1000).toISOString().slice(0, 16).replace('T', ' ') }),
      rows.length === all.length ? '' : t('feed.filter.shown', { n: rows.length }),
    ].filter(Boolean).join(' ');
    this._paint();
  }

  _paint() {
    render(html`<${Table} view=${this} />`, this.root);
  }
}
