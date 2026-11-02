"""Domain enums for intent, ticket, asset, approval and retrieval strategy."""

from enum import Enum


class AppEnv(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class IntentLabel(str, Enum):
    """Employee-facing IT service desk intents.

    The label set is deliberately narrower than a consumer-facing chatbot: an
    employee either asks a procedure question, asks about something they own
    (ticket / asset), or asks IT to change something (access / software /
    incident). Everything else is social, complaint, handoff or out of scope.
    """

    GREETING = "greeting"
    CHITCHAT = "chitchat"
    FAQ_POLICY = "faq_policy"
    TICKET_STATUS = "ticket_status"
    ASSET_QUERY = "asset_query"
    INCIDENT_REPORT = "incident_report"
    ACCESS_REQUEST = "access_request"
    SOFTWARE_REQUEST = "software_request"
    COMPLAINT = "complaint"
    HUMAN_HANDOFF = "human_handoff"
    OUT_OF_SCOPE = "out_of_scope"


class RetrievalStrategy(str, Enum):
    """Routing targets.

    DIRECT: parametric / greeting answers, no retrieval.
    SINGLE: one-shot hybrid retrieval.
    MULTI: Self-RAG iterative retrieval for multi-hop questions.
    AGENT: planner + tools, optionally with retrieval.
    REFUSE: query boundary / policy refusal.
    """

    DIRECT = "direct"
    SINGLE = "single"
    MULTI = "multi"
    AGENT = "agent"
    REFUSE = "refuse"


class QueryComplexity(str, Enum):
    SIMPLE = "simple"
    SINGLE_HOP = "single_hop"
    MULTI_HOP = "multi_hop"
    TOOL_REQUIRED = "tool_required"
    OUT_OF_SCOPE = "out_of_scope"


class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING_APPROVAL = "pending_approval"
    RESOLVED = "resolved"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class TicketPriority(str, Enum):
    """P1 blocks work, P2 degrades work, P3 is a normal request."""

    P1 = "p1"
    P2 = "p2"
    P3 = "p3"


class AssetStatus(str, Enum):
    IN_USE = "in_use"
    IN_STOCK = "in_stock"
    REPAIRING = "repairing"
    RETIRED = "retired"
    LOST = "lost"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    EXPIRED = "expired"


class ApprovalKind(str, Enum):
    """What the employee is asking IT to change."""

    ACCESS = "access"
    PASSWORD_RESET = "password_reset"
    VPN = "vpn"
    SOFTWARE_INSTALL = "software_install"
    ASSET_ISSUE = "asset_issue"


class ToolRisk(str, Enum):
    READ = "read"
    WRITE = "write"
    DESTRUCTIVE = "destructive"
    EXTERNAL = "external"


class CompressionLevel(str, Enum):
    NONE = "none"
    SOFT_TRUNCATE = "soft_truncate"
    HARD_COMPRESS = "hard_compress"
    AUTO_COMPACT = "auto_compact"


class DocumentCategory(str, Enum):
    """Knowledge base categories, aligned with service desk ticket categories."""

    ACCOUNT = "account"
    DEVICE = "device"
    NETWORK = "network"
    SOFTWARE = "software"
    SECURITY = "security"
    PROCESS = "process"
    FAQ = "faq"
