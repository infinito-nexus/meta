import { t } from '../i18n.js';

export class CiCoverage {
  static RANK = { hole: 0, maybe: 1, covered: 2 };

  static key(role, variant) {
    return `${role}#${variant === null ? 0 : variant}`;
  }

  // Args:
  //   snapshot: the JSON core's `python -m cli.meta.ci.variant_split snapshot`
  //     writes: per sweep the head the budget deploys, per row its round.
  // Returns: { deployed, candidates, counts }. deployed maps 'role#variant' to
  //   [{ row, modes }], every head row whose round brings that role up at that
  //   variant: test-e2e-playwright runs the specs of every role a round
  //   deploys, not only the row's own app. A row counts only when every
  //   sweep's head carries it, because one CI run plays one sweep. candidates
  //   holds the roles CI discovery plans at all, counts the variants per role
  //   the snapshot's tree declares.
  static read(snapshot) {
    if (!snapshot || typeof snapshot.sweeps !== 'object' || typeof snapshot.rounds !== 'object') {
      throw new Error(t('tests.ci.shape'));
    }
    const sweeps = Object.values(snapshot.sweeps);
    const seen = new Map();
    for (const [index, sweep] of sweeps.entries()) {
      for (const entry of sweep.head || []) {
        const row = CiCoverage.key(entry.apps, Number(entry.variant) || 0);
        if (!seen.has(row)) seen.set(row, { sweeps: new Set(), modes: new Set() });
        seen.get(row).sweeps.add(index);
        seen.get(row).modes.add(entry.mode);
      }
    }
    const deployed = new Map();
    for (const [row, { sweeps: carried, modes }] of seen) {
      const round = snapshot.rounds[row];
      if (carried.size < sweeps.length || !round) continue;
      for (const [role, variant] of Object.entries(round.active || {})) {
        const key = CiCoverage.key(role, variant);
        if (!deployed.has(key)) deployed.set(key, []);
        deployed.get(key).push({ row, modes: [...modes].sort() });
      }
    }
    return {
      deployed,
      candidates: new Set((snapshot.rows || []).map(row => row.name)),
      counts: snapshot.variant_counts || {},
    };
  }

  static _verdict(group, deployed) {
    const live = group.filter(row => (deployed.get(CiCoverage.key(row.role, row.variant)) || []).length);
    if (live.some(row => row.status === 'runs')) return 'covered';
    if (live.some(row => row.status === 'unknown')) return 'maybe';
    return 'hole';
  }

  // Args:
  //   rows: the Playwright rows, one per role, variant and test.
  //   branch: read() of the snapshot under review.
  //   base: read() of the snapshot it is compared with, or null.
  // Returns: rows, each given ci, the CI rows that deploy its role at its
  //   variant, and coverage, one verdict for the test across its variants:
  //   covered (a CI row runs it), maybe (only behind a gate the closure
  //   settles), hole (no CI row runs it), lost (base ran it, branch does
  //   less) or excluded (CI discovery leaves the role out on purpose).
  static annotate(rows, branch, base) {
    const groups = new Map();
    for (const row of rows) {
      row.ci = branch.deployed.get(CiCoverage.key(row.role, row.variant)) || [];
      const key = JSON.stringify([row.role, row.module, row.test]);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(row);
    }
    for (const group of groups.values()) {
      const now = CiCoverage._verdict(group, branch.deployed);
      const before = base ? CiCoverage._verdict(group, base.deployed) : now;
      let coverage = now;
      if (CiCoverage.RANK[now] < CiCoverage.RANK[before]) coverage = 'lost';
      else if (now === 'hole' && !branch.candidates.has(group[0].role)) coverage = 'excluded';
      for (const row of group) row.coverage = coverage;
    }
    return rows;
  }

  // Args:
  //   ci: the CI rows of one role and variant, as annotate() sets them.
  static describe(ci, separator) {
    return ci.length ? ci.map(one => `${one.row} (${one.modes.join('/')})`).join(separator) : t('tests.ci.none');
  }

  // Returns: one entry per test rather than per variant row, so the counts
  //   say how many tests CI runs.
  static tests(rows) {
    const tests = new Map();
    for (const row of rows) tests.set(JSON.stringify([row.role, row.module, row.test]), row);
    return [...tests.values()];
  }

  // Args:
  //   snapshot: read() output.
  //   served: role -> how many variants the served tree declares.
  // Returns: the roles whose variant count differs, where the snapshot's
  //   variant numbers may name other variants than the table's.
  static drift(snapshot, served) {
    return Object.entries(served)
      .filter(([role, count]) => role in snapshot.counts && snapshot.counts[role] !== Math.max(1, count))
      .map(([role]) => role)
      .sort();
  }
}
