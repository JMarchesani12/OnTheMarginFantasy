import { useEffect, useRef, useState } from "react";
import type { LeagueMember } from "../../types/leagueMember";

type DraftOrderEditorProps = {
  orderedMembers: LeagueMember[];
  memberCount: number;
  membersLoading: boolean;
  membersError: string | null;
  memberActionError: string | null;
  draggingMemberId: number | null;
  currentUserId: number | null;
  onMoveMember: (memberId: number, direction: -1 | 1) => void;
  onRandomize: () => void;
  onRemoveMember: (member: LeagueMember) => void | Promise<void>;
  onDragStart: (memberId: number) => void;
  onDragOver: (memberId: number) => void;
  onDragEnd: () => void;
};

export default function DraftOrderEditor({
  orderedMembers, memberCount, membersLoading, membersError, memberActionError,
  draggingMemberId, currentUserId, onRandomize, onRemoveMember,
  onDragStart, onDragOver, onDragEnd, onMoveMember,
}: DraftOrderEditorProps) {
  const moveButtons = useRef(new Map<string, HTMLButtonElement>());
  const pendingFocus = useRef<{ id: number; direction: -1 | 1 } | null>(null);
  const [announcement, setAnnouncement] = useState("");
  useEffect(() => {
    const pending = pendingFocus.current;
    pendingFocus.current = null;
    if (!pending) return;
    const index = orderedMembers.findIndex(member => member.id === pending.id);
    if (index < 0) return;
    const requested = moveButtons.current.get(`${pending.id}:${pending.direction}`);
    const opposite = moveButtons.current.get(`${pending.id}:${-pending.direction}`);
    const target = requested && !requested.disabled ? requested : opposite;
    if (target?.isConnected && !target.disabled) target.focus();
    const member = orderedMembers[index];
    setAnnouncement(`${member.teamName ?? `Member ${member.id}`} moved to position ${index + 1} of ${orderedMembers.length}.`);
  }, [orderedMembers]);
  return (
    <div className="ml-draft-order">
      <div className="ml-draft-order-header">
        <h3>Draft Order</h3>
        <button
          className="cl-btn-secondary"
          type="button"
          onClick={onRandomize}
          disabled={memberCount === 0}
        >
          Randomize Draft Order
        </button>
      </div>

      <p role="status" aria-live="polite" className="ml-muted">{announcement}</p>
      {membersLoading && (
        <p className="ml-muted">Loading league members…</p>
      )}
      {membersError && <p className="ml-error">{membersError}</p>}
      {memberActionError && (
        <p className="ml-error">{memberActionError}</p>
      )}

      {memberCount > 0 && (
        <div className="ml-draft-order-list">
          {orderedMembers.map((member, index) => (
            <div
              key={member.id}
              className={`ml-draft-order-row ${draggingMemberId === member.id ? "is-dragging" : ""}`}
              draggable
              onDragStart={() => onDragStart(member.id)}
              onDragOver={(event) => {
                event.preventDefault();
                onDragOver(member.id);
              }}
              onDragEnd={onDragEnd}
            >
              <div className="ml-draft-order-main">
                <span className="ml-draft-rank">
                  {index + 1}
                </span>
                <div>
                  <p className="ml-draft-member">
                    {member.teamName ?? `Member ${member.id}`}
                  </p>
                  <span className="ml-draft-sub">
                    {member.displayName}
                  </span>
                </div>
              </div>
              <div className="ml-draft-actions">
                <button
                  className="ml-remove-btn"
                  type="button"
                  onClick={() => onRemoveMember(member)}
                  disabled={member.userId === currentUserId}
                  title={
                    member.userId === currentUserId
                      ? "You cannot remove yourself."
                      : "Remove member"
                  }
                >
                  Remove
                </button>
                {([-1, 1] as const).map(direction => (
                  <button
                    key={direction}
                    type="button"
                    className="cl-btn-secondary"
                    aria-label={`Move ${member.teamName ?? `Member ${member.id}`} ${direction === -1 ? "up" : "down"}`}
                    disabled={direction === -1 ? index === 0 : index === orderedMembers.length - 1}
                    ref={node => {
                      const key = `${member.id}:${direction}`;
                      if (node) moveButtons.current.set(key, node);
                      else moveButtons.current.delete(key);
                    }}
                    onClick={() => {
                      if (direction === -1 ? index === 0 : index === orderedMembers.length - 1) return;
                      pendingFocus.current = { id: member.id, direction };
                      onMoveMember(member.id, direction);
                    }}
                  >{direction === -1 ? "Move up" : "Move down"}</button>
                ))}
                <span className="ml-drag-hint" aria-hidden="true">
                  ⇅
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
