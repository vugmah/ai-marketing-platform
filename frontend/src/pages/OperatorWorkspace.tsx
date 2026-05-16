import React, { useState, useEffect } from "react";
import {
  Box,
  Typography,
  Card,
  CardContent,
  Chip,
  Button,
  Tabs,
  Tab,
  Badge,
  LinearProgress,
  Alert,
  Tooltip,
  Divider,
  Grid,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  CircularProgress,
} from "@mui/material";
import {
  CheckCircle,
  Cancel,
  Send,
  Warning,
  TrendingUp,
  TrendingDown,
  RemoveRedEye,
  Message,
  NotificationsActive,
  Shield,
  Timer,
  Assessment,
} from "@mui/icons-material";

// Types
interface ApprovalRequest {
  id: number;
  platform: string;
  recipient_username: string;
  message_subject: string;
  message_body: string;
  message_type: string;
  status: "pending" | "approved" | "rejected" | "sent";
  confidence_score: number;
  moderation_score: number;
  moderation_category: string;
  flags: string[];
  requested_at: string;
  ai_suggested: boolean;
}

interface EngagementEvent {
  id: number;
  platform: string;
  event_type: string;
  follower_username: string;
  message_preview: string;
  sentiment: string;
  is_new_lead: boolean;
  event_date: string;
}

interface DeltaSummary {
  period_days: number;
  estimated_new_followers: number;
  estimated_unfollows: number;
  net_change: number;
  suspicious_events: number;
  average_confidence: number;
  note: string;
}

interface FollowerValue {
  tier: string;
  count: number;
  color: string;
}

interface GovernanceQuota {
  platform: string;
  daily_quota: number;
  sent_today: number;
  remaining: number;
  usage_percentage: number;
  status: string;
}

// Mock data
const mockApprovals: ApprovalRequest[] = [
  {
    id: 1,
    platform: "instagram",
    recipient_username: "ayse_tasarim",
    message_subject: "Hos Geldiniz",
    message_body: "Merhaba @ayse_tasarim! Bizi takip ettiginiz icin tesekkur ederiz. Yeni icerik ve kampanyalarimizdan haberdar olacaksiniz.",
    message_type: "welcome_new_follower",
    status: "pending",
    confidence_score: 0.82,
    moderation_score: 0.95,
    moderation_category: "compliant",
    flags: [],
    requested_at: "2026-05-16T10:30:00Z",
    ai_suggested: true,
  },
  {
    id: 2,
    platform: "whatsapp",
    recipient_username: "+905551234567",
    message_subject: "Ozel Kampanya",
    message_body: "Merhaba! Yeni kampanyalarimiz basladi. Size ozel firsatlari ogrenmek ister misiniz?",
    message_type: "campaign_suggestion",
    status: "pending",
    confidence_score: 0.71,
    moderation_score: 0.88,
    moderation_category: "compliant",
    flags: [],
    requested_at: "2026-05-16T11:15:00Z",
    ai_suggested: true,
  },
  {
    id: 3,
    platform: "facebook",
    recipient_username: "mehmet_teknoloji",
    message_subject: "Sizi Ozledik",
    message_body: "Merhaba @mehmet_teknoloji! Sizi aramizda ozledik. Yeni iceriklerimiz ve kampanyalarimiz var. Goz atmak isterseniz bizi takipte kalin.",
    message_type: "reengagement_for_low",
    status: "pending",
    confidence_score: 0.65,
    moderation_score: 0.92,
    moderation_category: "needs_review",
    flags: ["low_engagement_target"],
    requested_at: "2026-05-16T12:00:00Z",
    ai_suggested: true,
  },
];

const mockEngagements: EngagementEvent[] = [
  { id: 1, platform: "instagram", event_type: "new_dm", follower_username: "zeynep_moda", message_preview: "Urunler hakkinda bilgi alabilir miyim?", sentiment: "positive", is_new_lead: true, event_date: "2026-05-16T09:00:00Z" },
  { id: 2, platform: "whatsapp", event_type: "new_whatsapp_message", follower_username: "+905559998877", message_preview: "Fiyat listesi gonderebilir misiniz?", sentiment: "positive", is_new_lead: true, event_date: "2026-05-16T09:30:00Z" },
  { id: 3, platform: "facebook", event_type: "new_comment", follower_username: "can_kultur", message_preview: "Harika bir etkinlik olmus!", sentiment: "positive", is_new_lead: false, event_date: "2026-05-16T10:00:00Z" },
  { id: 4, platform: "instagram", event_type: "new_mention", follower_username: "eda_sanat", message_preview: "@firmamiz cok basarili", sentiment: "positive", is_new_lead: false, event_date: "2026-05-16T10:45:00Z" },
];

const mockDelta: DeltaSummary = {
  period_days: 30,
  estimated_new_followers: 245,
  estimated_unfollows: 89,
  net_change: 156,
  suspicious_events: 2,
  average_confidence: 0.78,
  note: "All unfollow counts are estimates, not definitive data.",
};

const mockValueTiers: FollowerValue[] = [
  { tier: "high_value", count: 234, color: "#4caf50" },
  { tier: "medium_value", count: 456, color: "#ff9800" },
  { tier: "low_value", count: 189, color: "#f44336" },
  { tier: "ghost", count: 67, color: "#9e9e9e" },
  { tier: "new", count: 112, color: "#2196f3" },
];

const mockQuotas: GovernanceQuota[] = [
  { platform: "instagram", daily_quota: 20, sent_today: 8, remaining: 12, usage_percentage: 40, status: "ok" },
  { platform: "facebook", daily_quota: 30, sent_today: 12, remaining: 18, usage_percentage: 40, status: "ok" },
  { platform: "tiktok", daily_quota: 10, sent_today: 1, remaining: 9, usage_percentage: 10, status: "ok" },
  { platform: "whatsapp", daily_quota: 50, sent_today: 15, remaining: 35, usage_percentage: 30, status: "ok" },
  { platform: "telegram", daily_quota: 40, sent_today: 10, remaining: 30, usage_percentage: 25, status: "ok" },
];

function TabPanel({ children, value, index }: { children: React.ReactNode; value: number; index: number }) {
  return value === index ? <Box sx={{ py: 2 }}>{children}</Box> : null;
}

function ConfidenceChip({ score }: { score: number }) {
  let color: "success" | "warning" | "error" = "success";
  let label = "High";
  if (score < 0.5) { color = "error"; label = "Low"; }
  else if (score < 0.75) { color = "warning"; label = "Medium"; }
  return <Chip size="small" color={color} label={`${label} (${(score * 100).toFixed(0)}%)`} />;
}

function StatusChip({ status }: { status: string }) {
  const colors: Record<string, any> = {
    pending: { color: "warning", icon: <Timer fontSize="small" /> },
    approved: { color: "success", icon: <CheckCircle fontSize="small" /> },
    rejected: { color: "error", icon: <Cancel fontSize="small" /> },
    sent: { color: "info", icon: <Send fontSize="small" /> },
  };
  const s = colors[status] || colors.pending;
  return <Chip size="small" color={s.color} icon={s.icon} label={status.toUpperCase()} />;
}

export default function OperatorWorkspace() {
  const [tab, setTab] = useState(0);
  const [selectedApproval, setSelectedApproval] = useState<ApprovalRequest | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [reviewNote, setReviewNote] = useState("");
  const [loading, setLoading] = useState(false);

  const pendingCount = mockApprovals.filter(a => a.status === "pending").length;

  const handleApprove = (id: number) => {
    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      setPreviewOpen(false);
    }, 500);
  };

  const handleReject = (id: number) => {
    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      setPreviewOpen(false);
    }, 500);
  };

  return (
    <Box sx={{ p: 3, maxWidth: 1400, mx: "auto" }}>
      {/* Header */}
      <Typography variant="h4" gutterBottom fontWeight="bold">
        <Message sx={{ mr: 1, verticalAlign: "middle" }} />
        Outreach Operator Workspace
      </Typography>
      <Typography variant="body2" color="text.secondary" gutterBottom>
        Safe messaging operations. All outbound messages require approval. Auto-send is disabled.
      </Typography>

      {/* Summary Cards */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" variant="body2">Pending Approvals</Typography>
              <Typography variant="h3" color="warning.main">
                <Badge badgeContent={pendingCount} color="warning">
                  <NotificationsActive fontSize="large" />
                </Badge>
                {pendingCount}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" variant="body2">Net Follower Change (30d)</Typography>
              <Typography variant="h3" color={mockDelta.net_change >= 0 ? "success.main" : "error.main"}>
                {mockDelta.net_change >= 0 ? "+" : ""}{mockDelta.net_change}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                +{mockDelta.estimated_new_followers} new / -{mockDelta.estimated_unfollows} est. lost
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" variant="body2">High-Value Followers</Typography>
              <Typography variant="h3" color="success.main">
                {mockValueTiers.find(t => t.tier === "high_value")?.count || 0}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Of {mockValueTiers.reduce((a, b) => a + b.count, 0)} total
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" variant="body2">Avg AI Confidence</Typography>
              <Typography variant="h3" color="info.main">
                {(mockDelta.average_confidence * 100).toFixed(0)}%
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Estimated data
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Safety Alert */}
      <Alert severity="info" sx={{ mb: 3 }} icon={<Shield />}>
        <strong>Safe Mode Active:</strong> Auto-send is disabled. All messages require manual approval.
        Rate limits: Instagram 5/min, WhatsApp 15/min. Daily quotas enforced.
      </Alert>

      {/* Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="scrollable">
          <Tab label={`Approval Inbox (${pendingCount})`} icon={<NotificationsActive fontSize="small" />} iconPosition="start" />
          <Tab label="Engagement Opportunities" icon={<TrendingUp fontSize="small" />} iconPosition="start" />
          <Tab label="Follower Intelligence" icon={<Assessment fontSize="small" />} iconPosition="start" />
          <Tab label="Outreach Analytics" icon={<RemoveRedEye fontSize="small" />} iconPosition="start" />
          <Tab label="Governance Quotas" icon={<Shield fontSize="small" />} iconPosition="start" />
        </Tabs>

        {/* Tab 1: Approval Inbox */}
        <TabPanel value={tab} index={0}>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>ID</TableCell>
                  <TableCell>Platform</TableCell>
                  <TableCell>Recipient</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>AI Confidence</TableCell>
                  <TableCell>Moderation</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {mockApprovals.map((a) => (
                  <TableRow key={a.id} hover>
                    <TableCell>#{a.id}</TableCell>
                    <TableCell>
                      <Chip size="small" label={a.platform} variant="outlined" />
                    </TableCell>
                    <TableCell>@{a.recipient_username}</TableCell>
                    <TableCell>{a.message_type.replace(/_/g, " ")}</TableCell>
                    <TableCell><ConfidenceChip score={a.confidence_score} /></TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        color={a.moderation_category === "compliant" ? "success" : a.moderation_category === "needs_review" ? "warning" : "error"}
                        label={`${a.moderation_category} (${(a.moderation_score * 100).toFixed(0)}%)`}
                      />
                    </TableCell>
                    <TableCell><StatusChip status={a.status} /></TableCell>
                    <TableCell>
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={<RemoveRedEye />}
                        onClick={() => { setSelectedApproval(a); setPreviewOpen(true); }}
                      >
                        Review
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </TabPanel>

        {/* Tab 2: Engagement Opportunities */}
        <TabPanel value={tab} index={1}>
          <Grid container spacing={2}>
            <Grid size={{ xs: 12, md: 6 }}>
              <Typography variant="h6" gutterBottom>New Engagements (Today)</Typography>
              {mockEngagements.map((e) => (
                <Card key={e.id} sx={{ mb: 1 }}>
                  <CardContent sx={{ py: 1, "&:last-child": { pb: 1 } }}>
                    <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <Box>
                        <Typography variant="subtitle2">
                          @{e.follower_username}
                          {e.is_new_lead && <Chip size="small" color="success" label="NEW LEAD" sx={{ ml: 1 }} />}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {e.platform} / {e.event_type} / {e.sentiment}
                        </Typography>
                      </Box>
                      <Button size="small" variant="contained" startIcon={<Message />}>
                        Respond
                      </Button>
                    </Box>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                      {e.message_preview}
                    </Typography>
                  </CardContent>
                </Card>
              ))}
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <Typography variant="h6" gutterBottom>AI Suggested Messages</Typography>
              {mockApprovals.filter(a => a.ai_suggested).map((a) => (
                <Card key={a.id} sx={{ mb: 1, borderLeft: 3, borderColor: "info.main" }}>
                  <CardContent sx={{ py: 1, "&:last-child": { pb: 1 } }}>
                    <Typography variant="subtitle2">{a.message_subject}</Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                      To: @{a.recipient_username} ({a.platform})
                    </Typography>
                    <Typography variant="body2" sx={{ mt: 0.5, fontStyle: "italic" }}>
                      &quot;{a.message_body.substring(0, 100)}...&quot;
                    </Typography>
                    <Box sx={{ mt: 1, display: "flex", gap: 1 }}>
                      <ConfidenceChip score={a.confidence_score} />
                      <Button size="small" variant="outlined">Preview</Button>
                      <Button size="small" variant="contained" color="success">Request Approval</Button>
                    </Box>
                  </CardContent>
                </Card>
              ))}
            </Grid>
          </Grid>
        </TabPanel>

        {/* Tab 3: Follower Intelligence */}
        <TabPanel value={tab} index={2}>
          <Grid container spacing={3}>
            <Grid size={{ xs: 12, md: 6 }}>
              <Typography variant="h6" gutterBottom>Follower Value Distribution</Typography>
              <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
                {mockValueTiers.map((t) => (
                  <Box key={t.tier} sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                    <Box sx={{ width: 100 }}>
                      <Typography variant="body2" fontWeight="bold" sx={{ textTransform: "capitalize" }}>
                        {t.tier.replace("_", " ")}
                      </Typography>
                    </Box>
                    <Box sx={{ flex: 1 }}>
                      <LinearProgress
                        variant="determinate"
                        value={(t.count / 1058) * 100}
                        sx={{
                          height: 20,
                          borderRadius: 1,
                          backgroundColor: "#f5f5f5",
                          "& .MuiLinearProgress-bar": { backgroundColor: t.color },
                        }}
                      />
                    </Box>
                    <Typography variant="body2" sx={{ width: 50, textAlign: "right" }}>{t.count}</Typography>
                  </Box>
                ))}
              </Box>
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <Typography variant="h6" gutterBottom>Estimated Unfollow Trend (30d)</Typography>
              <Card sx={{ bgcolor: "#fafafa" }}>
                <CardContent>
                  <Box sx={{ display: "flex", justifyContent: "space-between", mb: 2 }}>
                    <Box>
                      <Typography variant="body2" color="text.secondary">New Followers (Est.)</Typography>
                      <Typography variant="h5" color="success.main">
                        <TrendingUp fontSize="small" sx={{ verticalAlign: "middle" }} />
                        +{mockDelta.estimated_new_followers}
                      </Typography>
                    </Box>
                    <Box>
                      <Typography variant="body2" color="text.secondary">Est. Unfollows</Typography>
                      <Typography variant="h5" color="error.main">
                        <TrendingDown fontSize="small" sx={{ verticalAlign: "middle" }} />
                        -{mockDelta.estimated_unfollows}
                      </Typography>
                    </Box>
                    <Box>
                      <Typography variant="body2" color="text.secondary">Net Change</Typography>
                      <Typography variant="h5" color={mockDelta.net_change >= 0 ? "success.main" : "error.main"}>
                        {mockDelta.net_change >= 0 ? "+" : ""}{mockDelta.net_change}
                      </Typography>
                    </Box>
                  </Box>
                  {mockDelta.suspicious_events > 0 && (
                    <Alert severity="warning" icon={<Warning />} sx={{ mb: 1 }}>
                      {mockDelta.suspicious_events} suspicious unfollow spike(s) detected
                    </Alert>
                  )}
                  <Alert severity="info" icon={<Shield />}>
                    {mockDelta.note}
                  </Alert>
                  <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: "block" }}>
                    Avg confidence: {(mockDelta.average_confidence * 100).toFixed(0)}%
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </TabPanel>

        {/* Tab 4: Outreach Analytics */}
        <TabPanel value={tab} index={3}>
          <Grid container spacing={3}>
            <Grid size={{ xs: 12, md: 4 }}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>Response Rate</Typography>
                  <Typography variant="h2" color="success.main">18.5%</Typography>
                  <Typography variant="caption" color="text.secondary">
                    Based on 54 sent messages / 10 responses
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid size={{ xs: 12, md: 4 }}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>Block/Report Rate</Typography>
                  <Typography variant="h2" color="success.main">0.0%</Typography>
                  <Typography variant="caption" color="text.secondary">
                    No blocks or reports (pilot safety)
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid size={{ xs: 12, md: 4 }}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>AI Usefulness</Typography>
                  <Typography variant="h2" color="info.main">76%</Typography>
                  <Typography variant="caption" color="text.secondary">
                    Operator approval rate for AI suggestions
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
          <Box sx={{ mt: 3 }}>
            <Typography variant="h6" gutterBottom>Platform Performance</Typography>
            <TableContainer component={Paper}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Platform</TableCell>
                    <TableCell align="right">Sent</TableCell>
                    <TableCell align="right">Delivered</TableCell>
                    <TableCell align="right">Responses</TableCell>
                    <TableCell align="right">Response Rate</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {["Instagram", "Facebook", "WhatsApp", "Telegram", "TikTok"].map((p) => (
                    <TableRow key={p}>
                      <TableCell>{p}</TableCell>
                      <TableCell align="right">{Math.floor(Math.random() * 20) + 5}</TableCell>
                      <TableCell align="right">{Math.floor(Math.random() * 18) + 5}</TableCell>
                      <TableCell align="right">{Math.floor(Math.random() * 5) + 1}</TableCell>
                      <TableCell align="right">{(Math.random() * 25 + 5).toFixed(1)}%</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        </TabPanel>

        {/* Tab 5: Governance Quotas */}
        <TabPanel value={tab} index={4}>
          <Alert severity="info" sx={{ mb: 2 }}>
            Conservative quotas for pilot. Warm-up phase: gradual increase over first 7 days.
          </Alert>
          <Grid container spacing={2}>
            {mockQuotas.map((q) => (
              <Grid size={{ xs: 12, sm: 6, md: 4 }} key={q.platform}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" sx={{ textTransform: "capitalize" }}>{q.platform}</Typography>
                    <Box sx={{ mt: 2 }}>
                      <Box sx={{ display: "flex", justifyContent: "space-between", mb: 1 }}>
                        <Typography variant="body2">Daily Quota</Typography>
                        <Typography variant="body2" fontWeight="bold">{q.sent_today} / {q.daily_quota}</Typography>
                      </Box>
                      <LinearProgress
                        variant="determinate"
                        value={q.usage_percentage}
                        color={q.usage_percentage > 80 ? "error" : q.usage_percentage > 60 ? "warning" : "success"}
                        sx={{ height: 10, borderRadius: 1 }}
                      />
                      <Box sx={{ display: "flex", justifyContent: "space-between", mt: 1 }}>
                        <Typography variant="caption" color="text.secondary">
                          {q.usage_percentage}% used
                        </Typography>
                        <Typography variant="caption" color="success.main">
                          {q.remaining} remaining
                        </Typography>
                      </Box>
                    </Box>
                    <Box sx={{ mt: 1 }}>
                      <Chip
                        size="small"
                        color={q.status === "ok" ? "success" : "warning"}
                        label={q.status.toUpperCase()}
                      />
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
          <Box sx={{ mt: 3 }}>
            <Typography variant="h6" gutterBottom>Cadence Rules</Typography>
            <TableContainer component={Paper}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Platform</TableCell>
                    <TableCell>Min Interval</TableCell>
                    <TableCell>Max/Week</TableCell>
                    <TableCell>Restrictions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  <TableRow>
                    <TableCell>Instagram</TableCell>
                    <TableCell>2 min</TableCell>
                    <TableCell>3</TableCell>
                    <TableCell>Mutual follow required</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Facebook</TableCell>
                    <TableCell>1 min</TableCell>
                    <TableCell>4</TableCell>
                    <TableCell>Page connection required</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>TikTok</TableCell>
                    <TableCell>5 min</TableCell>
                    <TableCell>2</TableCell>
                    <TableCell>Mutual follow, no links</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>WhatsApp</TableCell>
                    <TableCell>30 sec</TableCell>
                    <TableCell>5</TableCell>
                    <TableCell>Opt-in required</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Telegram</TableCell>
                    <TableCell>30 sec</TableCell>
                    <TableCell>5</TableCell>
                    <TableCell>Bot start required</TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        </TabPanel>
      </Paper>

      {/* Approval Preview Dialog */}
      <Dialog open={previewOpen} onClose={() => setPreviewOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>
          Review Message
          {selectedApproval && <StatusChip status={selectedApproval.status} />}
        </DialogTitle>
        <DialogContent>
          {selectedApproval && (
            <Box sx={{ pt: 1 }}>
              <Alert severity={selectedApproval.confidence_score >= 0.75 ? "success" : "warning"} sx={{ mb: 2 }}>
                <strong>AI Confidence:</strong> {(selectedApproval.confidence_score * 100).toFixed(0)}% / 
                <strong>Moderation:</strong> {selectedApproval.moderation_category} ({(selectedApproval.moderation_score * 100).toFixed(0)}%)
              </Alert>
              <Typography variant="subtitle2" color="text.secondary">To</Typography>
              <Typography variant="body1" gutterBottom>@{selectedApproval.recipient_username} ({selectedApproval.platform})</Typography>
              <Typography variant="subtitle2" color="text.secondary">Subject</Typography>
              <Typography variant="body1" gutterBottom>{selectedApproval.message_subject}</Typography>
              <Typography variant="subtitle2" color="text.secondary">Message</Typography>
              <Paper sx={{ p: 2, bgcolor: "#f5f5f5", mb: 2 }}>
                <Typography variant="body1">{selectedApproval.message_body}</Typography>
              </Paper>
              {selectedApproval.flags.length > 0 && (
                <Alert severity="warning" sx={{ mb: 2 }}>
                  Flags: {selectedApproval.flags.join(", ")}
                </Alert>
              )}
              <TextField
                fullWidth
                multiline
                rows={2}
                label="Review Note (optional)"
                value={reviewNote}
                onChange={(e) => setReviewNote(e.target.value)}
                placeholder="Add note for this decision..."
              />
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPreviewOpen(false)}>Cancel</Button>
          <Button
            onClick={() => selectedApproval && handleReject(selectedApproval.id)}
            color="error"
            variant="outlined"
            startIcon={<Cancel />}
            disabled={loading}
          >
            Reject
          </Button>
          <Button
            onClick={() => selectedApproval && handleApprove(selectedApproval.id)}
            color="success"
            variant="contained"
            startIcon={<CheckCircle />}
            disabled={loading}
          >
            {loading ? <CircularProgress size={20} /> : "Approve"}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
