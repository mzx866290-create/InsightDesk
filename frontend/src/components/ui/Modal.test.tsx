import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it } from 'vitest';
import { useState } from 'react';

import { Modal } from './Modal';

function ModalHarness() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        Open dialog
      </button>
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Accessible dialog"
        closeLabel="Close accessible dialog"
      >
        <button type="button">First action</button>
        <button type="button">Last action</button>
      </Modal>
    </>
  );
}

describe('Modal', () => {
  afterEach(() => {
    cleanup();
    document.body.style.overflow = '';
  });

  it('exposes dialog semantics, traps focus, locks scroll, and restores focus on Escape', async () => {
    const user = userEvent.setup();
    render(<ModalHarness />);

    const opener = screen.getByRole('button', { name: 'Open dialog' });
    await user.click(opener);

    const dialog = screen.getByRole('dialog', { name: 'Accessible dialog' });
    const closeButton = screen.getByRole('button', { name: 'Close accessible dialog' });
    const lastAction = screen.getByRole('button', { name: 'Last action' });

    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(document.body.style.overflow).toBe('hidden');
    await waitFor(() => expect(closeButton).toHaveFocus());

    lastAction.focus();
    await user.tab();
    expect(closeButton).toHaveFocus();

    await user.tab({ shift: true });
    expect(lastAction).toHaveFocus();

    await user.keyboard('{Escape}');

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(document.body.style.overflow).toBe('');
    expect(opener).toHaveFocus();
  });
});
