interface ModalProps {
  title: string;
  visible: boolean;
  onCancel: VoidFunction;
  index: number;
  submitAddons: VoidFunction;
  disabled: boolean;
  cancelSubPlan: VoidFunction;
}
