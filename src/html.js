import htm from './vendor/htm/htm.module.js';
import { h, render } from './vendor/preact/preact.module.js';
import { useState } from './vendor/preact/hooks.module.js';

export const html = htm.bind(h);
export { render, useState };

// Returns: the element a stateless vnode renders to, for callers that still
//   assemble the page by hand. A vnode holding state must stay in the
//   container it was rendered into, so it never comes through here.
export function toElement(vnode) {
  const box = document.createElement('div');
  render(vnode, box);
  return box.firstChild;
}
