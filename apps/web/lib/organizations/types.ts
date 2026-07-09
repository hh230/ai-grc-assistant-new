export interface Organization {
  id: string;
  name: string;
  orgType: string;
  industry: string;
  createdByUserId: string;
  createdAt: string;
}

/** An organization the current user belongs to, with their role in it. */
export interface OrganizationMembership extends Organization {
  role: string;
}

/** A real member of an organization's team, for the Settings > Team page. */
export interface OrganizationMember {
  userId: string;
  name: string;
  email: string;
  role: string;
  joinedAt: string;
}

/** An outstanding team invite that hasn't been accepted (or has expired) yet — shown
 * alongside real members so an owner/admin can see who's still pending. */
export interface PendingTeamInvitation {
  id: string;
  email: string;
  invitedRole: string;
  expiresAt: string;
  createdAt: string;
}

export interface OrganizationTeam {
  members: OrganizationMember[];
  pendingInvitations: PendingTeamInvitation[];
}
