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
