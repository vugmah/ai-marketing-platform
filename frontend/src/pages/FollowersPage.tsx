import React, { useState, useEffect } from 'react';
import { Box, Typography, Paper, Grid, Card, CardContent, CircularProgress, Alert, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Chip } from '@mui/material';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { apiClient } from '../api';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

interface FollowerData {
  totalFollowers: number;
  newFollowers: number;
  churnedFollowers: number;
  engagementRate: number;
  growthRate: number;
  healthScore: number;
}

interface FollowerTrend {
  date: string;
  followers: number;
  engagement: number;
}

const FollowersPage: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<FollowerData | null>(null);
  const [trends, setTrends] = useState<FollowerTrend[]>([]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [overviewRes, trendsRes] = await Promise.all([
          apiClient.get('/api/v2/followers/overview'),
          apiClient.get('/api/v2/followers/trends'),
        ]);
        setData(overviewRes.data);
        setTrends(trendsRes.data?.trends || []);
      } catch (err: any) {
        setError(err.response?.data?.message || 'Failed to load follower data');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) return <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}><CircularProgress /></Box>;
  if (error) return <Alert severity="error" sx={{ m: 2 }}>{error}</Alert>;

  const chartData = {
    labels: trends.map(t => t.date),
    datasets: [
      {
        label: 'Followers',
        data: trends.map(t => t.followers),
        borderColor: 'rgb(75, 192, 192)',
        tension: 0.1,
      },
      {
        label: 'Engagement %',
        data: trends.map(t => t.engagement),
        borderColor: 'rgb(255, 99, 132)',
        tension: 0.1,
      },
    ],
  };

  const getHealthColor = (score: number) => {
    if (score >= 80) return 'success';
    if (score >= 50) return 'warning';
    return 'error';
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>Follower Intelligence</Typography>
      
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card><CardContent>
            <Typography variant="h6">{data?.totalFollowers?.toLocaleString() || 0}</Typography>
            <Typography color="textSecondary">Total Followers</Typography>
          </CardContent></Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card><CardContent>
            <Typography variant="h6" color="success.main">+{data?.newFollowers || 0}</Typography>
            <Typography color="textSecondary">New This Week</Typography>
          </CardContent></Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card><CardContent>
            <Typography variant="h6" color="error.main">-{data?.churnedFollowers || 0}</Typography>
            <Typography color="textSecondary">Churned</Typography>
          </CardContent></Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card><CardContent>
            <Chip label={`${data?.healthScore || 0}/100`} color={getHealthColor(data?.healthScore || 0) as any} />
            <Typography color="textSecondary">Health Score</Typography>
          </CardContent></Card>
        </Grid>
      </Grid>

      <Paper sx={{ p: 2, mb: 3 }}>
        <Typography variant="h6" gutterBottom>Follower Trends</Typography>
        <Line data={chartData} options={{ responsive: true, maintainAspectRatio: false }} height={300} />
      </Paper>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Metric</TableCell>
              <TableCell>Value</TableCell>
              <TableCell>Status</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            <TableRow>
              <TableCell>Engagement Rate</TableCell>
              <TableCell>{data?.engagementRate?.toFixed(2) || 0}%</TableCell>
              <TableCell><Chip size="small" label={data?.engagementRate && data.engagementRate > 3 ? 'Good' : 'Needs Work'} color={data?.engagementRate && data.engagementRate > 3 ? 'success' : 'warning'} /></TableCell>
            </TableRow>
            <TableRow>
              <TableCell>Growth Rate</TableCell>
              <TableCell>{data?.growthRate?.toFixed(2) || 0}%</TableCell>
              <TableCell><Chip size="small" label={data?.growthRate && data.growthRate > 0 ? 'Growing' : 'Declining'} color={data?.growthRate && data.growthRate > 0 ? 'success' : 'error'} /></TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
};

export default FollowersPage;
