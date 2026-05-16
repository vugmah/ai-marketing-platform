import React from 'react';
import { Box, CircularProgress, Typography, Skeleton } from '@mui/material';

interface LoadingStateProps {
  message?: string;
  type?: 'spinner' | 'skeleton' | 'inline';
  count?: number;
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  message = 'Loading...',
  type = 'spinner',
  count = 3,
}) => {
  if (type === 'skeleton') {
    return (
      <Box sx={{ p: 2 }}>
        {Array.from({ length: count }).map((_, i) => (
          <Skeleton key={i} variant="rectangular" height={60} sx={{ mb: 1, borderRadius: 1 }} />
        ))}
      </Box>
    );
  }

  if (type === 'inline') {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <CircularProgress size={16} />
        <Typography variant="body2" color="textSecondary">{message}</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 200 }}>
      <CircularProgress size={40} sx={{ mb: 2 }} />
      <Typography variant="body1" color="textSecondary">{message}</Typography>
    </Box>
  );
};

export default LoadingState;
