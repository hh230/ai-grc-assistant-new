/**
 * Frameworks-as-data (CLAUDE.md §13). A canonical, configuration-driven catalog of
 * frameworks → controls. Pure data + lookups, no framework name hardcoded into control
 * flow. Consumed by Evidence (control linkage), Governance (coverage), and Risk (mitigating
 * controls). Adding a framework here requires no architectural change.
 *
 * The seed is a representative (not exhaustive) subset of each standard.
 */

export interface FrameworkControl {
  /** Stable global id, e.g. "iso_27001:A.5.15". */
  id: string;
  /** Human control code within the framework, e.g. "A.5.15". */
  code: string;
  title: string;
  description: string;
}

export interface Framework {
  id: string;
  name: string;
  shortName: string;
  region: string;
  controls: FrameworkControl[];
}

function control(
  frameworkId: string,
  code: string,
  title: string,
  description: string,
): FrameworkControl {
  return { id: `${frameworkId}:${code}`, code, title, description };
}

const ISO = "iso_27001";
const NCA = "nca_ecc";
const NIST = "nist_csf";

export const FRAMEWORKS: Framework[] = [
  {
    id: ISO,
    name: "ISO/IEC 27001:2022",
    shortName: "ISO 27001",
    region: "International",
    controls: [
      control(
        ISO,
        "A.5.1",
        "Policies for information security",
        "Information security policy and topic-specific policies are defined, approved, and reviewed.",
      ),
      control(
        ISO,
        "A.5.15",
        "Access control",
        "Rules to control physical and logical access to information based on business and security requirements.",
      ),
      control(ISO, "A.5.16", "Identity management", "The full lifecycle of identities is managed."),
      control(
        ISO,
        "A.5.17",
        "Authentication information",
        "Allocation and management of authentication information is controlled.",
      ),
      control(
        ISO,
        "A.5.18",
        "Access rights",
        "Access rights are provisioned, reviewed, modified, and removed per policy.",
      ),
      control(
        ISO,
        "A.5.23",
        "Information security for cloud services",
        "Acquisition, use, and exit of cloud services follow security requirements.",
      ),
      control(
        ISO,
        "A.5.30",
        "ICT readiness for business continuity",
        "ICT readiness is planned, implemented, and tested for continuity.",
      ),
      control(
        ISO,
        "A.8.2",
        "Privileged access rights",
        "The allocation and use of privileged access rights is restricted and managed.",
      ),
      control(
        ISO,
        "A.8.5",
        "Secure authentication",
        "Secure authentication technologies and procedures are implemented.",
      ),
      control(
        ISO,
        "A.8.15",
        "Logging",
        "Logs recording activities, exceptions, and events are produced, stored, and reviewed.",
      ),
      control(
        ISO,
        "A.8.16",
        "Monitoring activities",
        "Networks, systems, and applications are monitored for anomalous behaviour.",
      ),
      control(
        ISO,
        "A.8.24",
        "Use of cryptography",
        "Rules for the effective use of cryptography, including key management, are defined.",
      ),
    ],
  },
  {
    id: NCA,
    name: "NCA Essential Cybersecurity Controls",
    shortName: "NCA ECC",
    region: "Saudi Arabia",
    controls: [
      control(
        NCA,
        "1-1",
        "Cybersecurity Governance",
        "A cybersecurity strategy, policies, and roles are defined and approved by leadership.",
      ),
      control(
        NCA,
        "2-2",
        "Identity and Access Management",
        "Logical access is managed with least privilege, periodic review, and MFA for sensitive access.",
      ),
      control(
        NCA,
        "2-3",
        "Information System Protection",
        "Systems are hardened, patched, and protected against malware.",
      ),
      control(
        NCA,
        "2-5",
        "Network Security Management",
        "Networks are segmented and protected with appropriate controls.",
      ),
      control(
        NCA,
        "2-7",
        "Data and Information Protection",
        "Data is classified and protected throughout its lifecycle.",
      ),
      control(
        NCA,
        "2-8",
        "Cryptography",
        "Approved cryptographic standards protect data in transit and at rest.",
      ),
      control(
        NCA,
        "2-10",
        "Event Logs and Monitoring",
        "Security events are logged, retained, and monitored.",
      ),
      control(
        NCA,
        "2-12",
        "Vulnerability Management",
        "Vulnerabilities are identified, assessed, and remediated.",
      ),
      control(NCA, "2-13", "Penetration Testing", "Penetration tests are conducted periodically."),
      control(
        NCA,
        "4-1",
        "Third-Party Cybersecurity",
        "Third-party and outsourcing risks are assessed and managed.",
      ),
    ],
  },
  {
    id: NIST,
    name: "NIST Cybersecurity Framework 2.0",
    shortName: "NIST CSF",
    region: "International",
    controls: [
      control(
        NIST,
        "GV.RR",
        "Roles, Responsibilities & Authorities",
        "Cybersecurity roles and responsibilities are established and communicated.",
      ),
      control(
        NIST,
        "ID.AM",
        "Asset Management",
        "Assets are inventoried and managed consistent with their risk.",
      ),
      control(
        NIST,
        "PR.AA",
        "Identity Management & Access Control",
        "Access to assets is limited to authorized users, processes, and devices.",
      ),
      control(
        NIST,
        "PR.DS",
        "Data Security",
        "Data is managed consistent with the organization's risk strategy.",
      ),
      control(
        NIST,
        "DE.CM",
        "Continuous Monitoring",
        "Assets are monitored to find anomalies and potential incidents.",
      ),
      control(NIST, "RS.MA", "Incident Management", "Responses to detected incidents are managed."),
      control(
        NIST,
        "RC.RP",
        "Incident Recovery Plan Execution",
        "Recovery activities restore assets and operations after an incident.",
      ),
    ],
  },
];

const CONTROL_INDEX = new Map<string, { control: FrameworkControl; framework: Framework }>();
for (const framework of FRAMEWORKS) {
  for (const ctrl of framework.controls) {
    CONTROL_INDEX.set(ctrl.id, { control: ctrl, framework });
  }
}

export interface CatalogControl extends FrameworkControl {
  frameworkId: string;
  frameworkShortName: string;
}

export function allControls(): CatalogControl[] {
  return FRAMEWORKS.flatMap((framework) =>
    framework.controls.map((ctrl) => ({
      ...ctrl,
      frameworkId: framework.id,
      frameworkShortName: framework.shortName,
    })),
  );
}

export function getControl(id: string): CatalogControl | null {
  const entry = CONTROL_INDEX.get(id);
  if (!entry) return null;
  return {
    ...entry.control,
    frameworkId: entry.framework.id,
    frameworkShortName: entry.framework.shortName,
  };
}

export function isKnownControl(id: string): boolean {
  return CONTROL_INDEX.has(id);
}
