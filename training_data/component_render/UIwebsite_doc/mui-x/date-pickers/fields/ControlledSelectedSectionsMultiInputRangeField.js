import * as React from 'react';
import Typography from '@mui/material/Typography';
import Stack from '@mui/material/Stack';
import Button from '@mui/material/Button';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';

import { MultiInputDateRangeField } from '@mui/x-date-pickers-pro/MultiInputDateRangeField';

export default function ControlledSelectedSectionsMultiInputRangeField() {
  const [selectedSections, setSelectedSections] = React.useState(null);
  const startInputRef = React.useRef(null);
  const endInputRef = React.useRef(null);

  const setSelectedSectionType = (selectedSectionType, position) => {
    if (position === 'start') {
      startInputRef.current?.focus();
    } else {
      endInputRef.current?.focus();
    }
    setSelectedSections(selectedSectionType);
  };

  const renderDateHeader = (position) => (
    <Stack spacing={2} alignItems="center">
      <Typography textTransform="capitalize">{position}</Typography>
      <Stack direction="row" spacing={1}>
        {['month', 'day', 'year'].map((sectionName) => (
          <Button
            size="small"
            variant="outlined"
            onClick={() => setSelectedSectionType(sectionName, position)}
          >
            {sectionName}
          </Button>
        ))}
      </Stack>
    </Stack>
  );

  return (
    <LocalizationProvider dateAdapter={AdapterDayjs}>
      <Stack spacing={2}>
        <Stack spacing={2} justifyContent="space-between">
          {renderDateHeader('start')}
          {renderDateHeader('end')}
        </Stack>
        <MultiInputDateRangeField
          sx={{ minWidth: 300 }}
          slotProps={{
            textField: (ownerState) => ({
              inputRef:
                ownerState.position === 'start' ? startInputRef : endInputRef,
            }),
          }}
          selectedSections={selectedSections}
          onSelectedSectionsChange={setSelectedSections}
        />
      </Stack>
    </LocalizationProvider>
  );
}
