import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  styled,
} from '@mui/material';
import Rating from '@mui/material/Rating';
import SentimentVeryDissatisfiedIcon from '@mui/icons-material/SentimentVeryDissatisfied';
import SentimentDissatisfiedIcon from '@mui/icons-material/SentimentDissatisfied';
import SentimentSatisfiedIcon from '@mui/icons-material/SentimentSatisfied';
import SentimentSatisfiedAltIcon from '@mui/icons-material/SentimentSatisfiedAltOutlined';
import SentimentVerySatisfiedIcon from '@mui/icons-material/SentimentVerySatisfied';

const StyledRating = styled(Rating)(({ theme }) => ({
  '& .MuiRating-iconEmpty .MuiSvgIcon-root': {
    color: theme.palette.grey[300],
  },
  transition: 'transform 0.3s',
  '&:hover': {
    transform: 'scale(1.1)',
  },
}));

const customIcons = {
  1: {
    icon: <SentimentVeryDissatisfiedIcon color="error" />, label: 'Very Dissatisfied',
  },
  2: {
    icon: <SentimentDissatisfiedIcon color="warning" />, label: 'Dissatisfied',
  },
  3: {
    icon: <SentimentSatisfiedIcon color="info" />, label: 'Neutral',
  },
  4: {
    icon: <SentimentSatisfiedAltIcon color="success" />, label: 'Satisfied',
  },
  5: {
    icon: <SentimentVerySatisfiedIcon color="primary" />, label: 'Very Satisfied',
  },
};

function IconContainer(props) {
  const { value, ...other } = props;
  return <span {...other}>{customIcons[value].icon}</span>;
}

IconContainer.propTypes = {
  value: PropTypes.number.isRequired,
};

export default function MoodTracker() {
  const [value, setValue] = useState(2);
  const [open, setOpen] = useState(false);

  const handleRatingChange = (newValue) => {
    setValue(newValue);
    setOpen(true);
  };

  const handleClose = () => setOpen(false);

  return (
    <div style={{ maxWidth: 600, margin: 'auto', textAlign: 'center', padding: '20px', background: 'linear-gradient(to top right, #ffcc80, #ffa726)' }}>
      <h2>Mood Tracker</h2>
      <StyledRating
        name="customized-mood"
        defaultValue={2}
        value={value}
        onChange={(event, newValue) => handleRatingChange(newValue)}
        IconContainerComponent={IconContainer}
        highlightSelectedOnly
        getLabelText={(value) => customIcons[value].label}
      />
      <Dialog open={open} onClose={handleClose}>
        <DialogTitle>Your Mood</DialogTitle>
        <DialogContent>
          Are you sure you want to save this mood as {customIcons[value].label}?
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClose} color="primary">
            Cancel
          </Button>
          <Button onClick={handleClose} color="primary" autoFocus>
            Save
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  );
}