/* eslint-disable jsx-a11y/label-has-associated-control */
import React, { useState } from "react";
import { Button, Modal, Select, Input } from "antd";

interface RecurringChargesFormProps {
  visible: boolean;
  onClose: VoidFunction;
  preferredCurrency: string;
  submitHandler: (
    name: string,
    charge_timing: string,
    amount: number,
    charge_behaviour: string
  ) => void;
}
const RecurringChargesForm = ({
  visible,
  onClose,
  preferredCurrency,
  submitHandler,
}: RecurringChargesFormProps) => {
  const [chargeName, setChargeName] = useState("");
  const [amount, setAmount] = useState(0);
  const [chargeTiming, setChargeTiming] = useState("");
  const [chargeBehavior, setChargeBehaviour] = useState("");
  return (
    <Modal
      visible={visible}
      title="Add Recurring Charge"
      okText="Add Recurring Charge"
      okType="default"
      cancelText="Cancel"
      okButtonProps={{
        className: "!bg-gold !text-white !border-none",
      }}
      onCancel={onClose}
      onOk={() => {
        //
      }}
    >
      <div>
        <div>
          <label className="font-alliance mb-4 required">Charge Name</label>
          <Input
            className="!mt-4"
            placeholder="Charge Name"
            onChange={(e) => setChargeName(e.target.value)}
          />
        </div>
      </div>
    </Modal>
  );
};
export default RecurringChargesForm;
