import { describe, expect, it } from 'vitest';

import { chat, createSession, getHealth, listSessions } from './api';

describe('api contracts', () => {
  it('has exported functions', () => {
    expect(typeof getHealth).toBe('function');
    expect(typeof listSessions).toBe('function');
    expect(typeof createSession).toBe('function');
    expect(typeof chat).toBe('function');
  });
});
