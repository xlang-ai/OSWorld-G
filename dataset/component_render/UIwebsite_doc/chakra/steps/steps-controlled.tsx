"use client"

import { Button, Group } from "@chakra-ui/react"
import {
  StepsCompletedContent,
  StepsContent,
  StepsItem,
  StepsList,
  StepsNextTrigger,
  StepsPrevTrigger,
  StepsRoot,
} from "compositions/ui/steps"
import { useState } from "react"

export const StepsControlled = () => {
  const [step, setStep] = useState(1)

  return (
    <StepsRoot step={step} onStepChange={(e) => setStep(e.step)} count={3}>
      <StepsList>
        <StepsItem index={0} title="Step 1" />
        <StepsItem index={1} title="Step 2" />
        <StepsItem index={2} title="Step 3" />
      </StepsList>

      <StepsContent index={0}>Step 1</StepsContent>
      <StepsContent index={1}>Step 2</StepsContent>
      <StepsContent index={2}>Step 3</StepsContent>
      <StepsCompletedContent>All steps are complete!</StepsCompletedContent>

      <Group>
        <StepsPrevTrigger asChild>
          <Button variant="outline" size="sm">
            Prev
          </Button>
        </StepsPrevTrigger>
        <StepsNextTrigger asChild>
          <Button variant="outline" size="sm">
            Next
          </Button>
        </StepsNextTrigger>
      </Group>
    </StepsRoot>
  )
}
