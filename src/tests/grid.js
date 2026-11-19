import { html } from '../html.js';
import { t } from '../i18n.js';
import { TestsCatalog } from './catalog.js';
import { CiCoverage } from './coverage.js';
import { RunCell, RunMark, RunPicker } from './runCard.js';

// Args (props):
//   view: the TestsView the picked snapshot files are handed to.
function SnapshotPicker({ view }) {
  const pick = side => event => view.loadSnapshot(side, event.currentTarget.files[0]);
  return html`
    <div class="tests-run">
      ${['branch', 'base'].map(side => html`
        <label>
          ${t(`tests.ci.pick.${side}`)}
          <input type="file" accept=".json,application/json" class="form-control form-control-sm"
                 onChange=${pick(side)} />
        </label>
      `)}
    </div>
  `;
}

// Args (props):
//   ci: the CI rows that deploy the line's role at its variant.
function CiCell({ ci }) {
  return html`<th class=${ci.length ? 'tests-axis' : 'tests-axis ci-off'} title=${CiCoverage.describe(ci, '\n')}>
    ${ci.length ? String(ci.length) : ''}
  </th>`;
}

const cellClass = (row, ci) => {
  if (!ci) return `pw-${row.gate}`;
  return `pw-${row.gate} ci-${row.coverage}${row.ci.length ? '' : ' ci-off'}`;
};

// Args (props):
//   view: the TestsView whose lines, run and hover handlers the grid draws.
export function TestsGrid({ view }) {
  const { lines, width } = view;
  const held = view._held();
  const ci = view.kind === 'playwright' && Boolean(view.snapshots.branch);
  const axis = label => html`<th class="tests-axis">${label}</th>`;
  const line = entry => {
    const plan = view._plan(entry);
    const artifacts = held ? view.runs.of(entry.role, entry.variant) : [];
    return html`
      <tr class=${held && !artifacts.length ? 'tests-absent' : undefined}>
        <th class="tests-axis" data-role-name=${entry.role}>${view.roleInfo.labelNode(entry.role)}</th>
        ${axis(entry.variant === null ? t('tests.base') : String(entry.variant))}
        <th class="tests-axis" title=${plan ? undefined : t('tests.undeployed')}>
          ${plan ? String(plan.rank) : ''}
        </th>
        ${ci && html`<${CiCell} ci=${entry.cells[0].ci} />`}
        ${held && html`<${RunCell} artifacts=${artifacts} />`}
        ${Array.from({ length: width }, (_, index) => {
          const row = entry.cells[index];
          if (!row) return html`<td class="tests-blank"></td>`;
          if (artifacts.length) return html`<${RunMark} runs=${view.runs} row=${row} cell=${entry.keys[index]} />`;
          return html`<td class=${cellClass(row, ci)} data-cell=${entry.keys[index]}>${TestsCatalog.STATUS[row.gate].mark}</td>`;
        })}
      </tr>
    `;
  };
  return html`
    <h2>${t('view.testsWith', { view: t(`tests.kind.${view.kind}`) })}</h2>
    ${view.kind === 'playwright' && html`<${RunPicker} view=${view} />`}
    ${view.kind === 'playwright' && html`<${SnapshotPicker} view=${view} />`}
    <p class="table-note">${view.note}</p>
    <div class="table-scroll">
      ${lines && html`
        <table class="tests-matrix" onMouseOver=${event => view._hover(event)}
               onClick=${event => view._hover(event, true)} onMouseOut=${event => view._leave(event)}>
          <thead><tr>
            ${['role', 'variant', 'rank', ...(ci ? ['ci'] : []), ...(held ? ['run'] : [])].map(name => axis(t(`tests.axis.${name}`)))}
            ${Array.from({ length: width }, (_, index) => html`<th>${String(index + 1)}</th>`)}
          </tr></thead>
          <tbody>${lines.map(line)}</tbody>
        </table>
      `}
    </div>
  `;
}
