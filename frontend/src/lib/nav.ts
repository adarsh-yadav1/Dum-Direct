/** Only same-site paths are allowed as a return address, so a link cannot send people elsewhere. */
export function safeNext(value: string | null): string {
  return value && value.startsWith('/') && !value.startsWith('//') && !value.startsWith('/\\') ? value : '/'
}
