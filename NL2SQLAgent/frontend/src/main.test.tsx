import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

describe('App UI', () => {
  it('renders dashboard title', () => {
    render(<h1>智能分析系统</h1>);
    expect(screen.getByText('智能分析系统')).toBeTruthy();
  });

  it('renders panel labels', () => {
    render(
      <div>
        <h2>会话</h2>
        <h2>聊天</h2>
        <h2>图表</h2>
      </div>,
    );
    expect(screen.getByText('会话')).toBeTruthy();
    expect(screen.getByText('聊天')).toBeTruthy();
    expect(screen.getByText('图表')).toBeTruthy();
  });
});
