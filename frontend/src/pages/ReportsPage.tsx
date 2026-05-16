import React, { useState } from 'react';
import {
  Box, Typography, Paper, Button, FormControl, InputLabel, Select, MenuItem,
  CircularProgress, Alert, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, Chip, Grid, Card, CardContent
} from '@mui/material';
import { apiClient } from '../api';

interface ReportJob {
  id: number;
  type: string;
  status: string;
  createdAt: string;
  downloadUrl?: string;
}

const ReportsPage: React.FC = () => {
  const [reportType, setReportType] = useState('analytics');
  const [format, setFormat] = useState('pdf');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jobs, setJobs] = useState<ReportJob[]>([]);
  const [generating, setGenerating] = useState(false);

  const handleGenerate = async () => {
    try {
      setGenerating(true);
      setError(null);
      const resp = await apiClient.post(`/api/v2/reports/generate?report_type=${reportType}&format=${format}`);
      setJobs(prev => [resp.data, ...prev]);
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to generate report');
    } finally {
      setGenerating(false);
    }
  };

  const handleDownload = (jobId: number) => {
    window.open(`${apiClient.defaults.baseURL}/api/v2/reports/download/${jobId}`, '_blank');
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'success';
      case 'failed': return 'error';
      case 'processing': return 'info';
      default: return 'default';
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>Reports & Export</Typography>

      <Grid container spacing={3}>
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>Generate Report</Typography>
            
            <FormControl fullWidth sx={{ mb: 2 }}>
              <InputLabel>Report Type</InputLabel>
              <Select value={reportType} onChange={e => setReportType(e.target.value)}>
                <MenuItem value="analytics">Analytics Summary</MenuItem>
                <MenuItem value="followers">Follower Report</MenuItem>
                <MenuItem value="campaigns">Campaign Report</MenuItem>
                <MenuItem value="revenue">Revenue Report</MenuItem>
                <MenuItem value="ai_usage">AI Usage Report</MenuItem>
                <MenuItem value="compliance">Compliance Report</MenuItem>
              </Select>
            </FormControl>

            <FormControl fullWidth sx={{ mb: 3 }}>
              <InputLabel>Format</InputLabel>
              <Select value={format} onChange={e => setFormat(e.target.value)}>
                <MenuItem value="pdf">PDF</MenuItem>
                <MenuItem value="csv">CSV</MenuItem>
                <MenuItem value="xlsx">Excel</MenuItem>
              </Select>
            </FormControl>

            <Button
              variant="contained"
              fullWidth
              onClick={handleGenerate}
              disabled={generating}
            >
              {generating ? <CircularProgress size={24} /> : 'Generate Report'}
            </Button>

            {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
          </Paper>
        </Grid>

        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>Recent Exports</Typography>
            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>ID</TableCell>
                    <TableCell>Type</TableCell>
                    <TableCell>Format</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Created</TableCell>
                    <TableCell>Action</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {jobs.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={6} align="center">No reports generated yet</TableCell>
                    </TableRow>
                  )}
                  {jobs.map(job => (
                    <TableRow key={job.id}>
                      <TableCell>{job.id}</TableCell>
                      <TableCell>{job.type}</TableCell>
                      <TableCell><Chip size="small" label={format.toUpperCase()} /></TableCell>
                      <TableCell><Chip size="small" label={job.status} color={getStatusColor(job.status) as any} /></TableCell>
                      <TableCell>{new Date(job.createdAt).toLocaleString()}</TableCell>
                      <TableCell>
                        {job.status === 'completed' && job.downloadUrl && (
                          <Button size="small" onClick={() => handleDownload(job.id)}>Download</Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        </Grid>
      </Grid>

      <Box sx={{ mt: 3 }}>
        <Grid container spacing={2}>
          {['analytics', 'followers', 'campaigns', 'revenue', 'ai_usage', 'compliance'].map(type => (
            <Grid item xs={6} sm={4} md={2} key={type}>
              <Card variant="outlined">
                <CardContent sx={{ textAlign: 'center', py: 1 }}>
                  <Typography variant="body2" color="textSecondary">
                    {type.replace('_', ' ').toUpperCase()}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      </Box>
    </Box>
  );
};

export default ReportsPage;
