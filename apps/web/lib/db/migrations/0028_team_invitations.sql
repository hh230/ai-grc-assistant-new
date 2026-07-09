-- Team invitations: an owner/admin invites someone directly into their *existing*
-- organization, as opposed to the original KI-P9 flow where accepting an invitation always
-- creates a brand-new organization. Nullable so the two flows share one table: NULL means
-- "create a new org on accept" (unchanged legacy behavior), set means "join this org, don't
-- create one" (see lib/invitations/service.ts#acceptInvitation).
ALTER TABLE invitations ADD COLUMN IF NOT EXISTS organization_id text REFERENCES organizations (id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS invitations_organization_id_idx ON invitations (organization_id);
