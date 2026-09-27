// Args:
//   path: the mirror route to read, query string included.
// Returns: the parsed body, or a rejection carrying the reason the mirror
//   named. The mirror answers its own failures 502 with that reason in the
//   body, so the status alone loses it.
export function ask(path) {
  return fetch(path).then(answer => answer.json().then(
    body => (answer.ok ? body : Promise.reject(new Error(body.error || `HTTP ${answer.status}`))),
    () => Promise.reject(new Error(`HTTP ${answer.status}`))
  ));
}
