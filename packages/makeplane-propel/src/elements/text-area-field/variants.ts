import { cva } from "class-variance-authority";

// The text area field's root: the label column sits 8px (`spacing/2`) above the control at every
// size, per the Text area set (2448:416); the shared `Field` frame steps 6/6/8/8.
export const textAreaFieldVariants = cva("flex flex-col gap-2");
