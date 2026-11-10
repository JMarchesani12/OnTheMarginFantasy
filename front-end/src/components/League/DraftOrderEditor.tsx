import type { LeagueMember } from "../../types/leagueMember";

type DraftOrderEditorProps = {
  orderedMembers: LeagueMember[];
  memberCount: number;
  membersLoading: boolean;
  membersError: string | null;
  memberActionError: string | null;
  draggingMemberId: number | null;
  currentUserId: number | null;
  onRandomize: () => void;
  onRemoveMember: (member: LeagueMember) => void | Promise<void>;
  onDragStart: (memberId: number) => void;
  onDragOver: (memberId: number) => void;
  onDragEnd: () => void;
};

export default function DraftOrderEditor({
  orderedMembers, memberCount, membersLoading, membersError, memberActionError,
  draggingMemberId, currentUserId, onRandomize, onRemoveMember,
  onDragStart, onDragOver, onDragEnd,
}: DraftOrderEditorProps) {
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
