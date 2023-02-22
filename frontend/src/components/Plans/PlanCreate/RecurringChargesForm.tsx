/* eslint-disable jsx-a11y/label-has-associated-control */
import React, { useState } from "react";
import { Button, Modal, Select, Input, InputNumber } from "antd";
import { constructBillType } from "../../Addons/AddonsDetails/AddOnInfo";
import capitalize from "../../../helpers/capitalize";
import { fourDP } from "../../../helpers/fourDP";

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
  const [amount, setAmount] = useState(0.0);
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
        submitHandler(chargeName, chargeTiming, amount, chargeBehavior);
        onClose();
      }}
    >
      <div>
        <div className="mt-4">
          <label className="font-alliance mb-4 required">Charge Name</label>
          <Input
            className="!mt-4"
            placeholder="Charge Name"
            value={chargeName}
            onChange={(e) => setChargeName(e.target.value)}
          />
        </div>
        <div className="mt-4">
          <label className="font-alliance mb-4 required">Cost</label>
          <div className="!mt-4 relative">
            <span className="z-10 absolute top-6 left-[2px]">
              {preferredCurrency}
            </span>
            <InputNumber
              value={amount}
              step=".01"
              max={999.9999}
              className="!w-full"
              onChange={(e) => setAmount(Number(e))}
            />
          </div>
          <div className="mt-4 flex gap-12">
            <div className="mt-4 flex flex-col">
              <label className="font-alliance mb-4 required">
                Charge Timing
              </label>
              <Select
                value={chargeTiming}
                placeholder="Charge Timing"
                className="w-full"
                onChange={(e) => setChargeTiming(e)}
              >
                {[
                  { id: 1, val: "in_arrears" },
                  { id: 2, val: "in_advance" },
                ].map((behaviour) => (
                  <Select.Option key={behaviour.id} value={behaviour.val}>
                    {constructBillType(capitalize(behaviour.val))}
                  </Select.Option>
                ))}
              </Select>
            </div>
            <div className="mt-4 flex flex-col ml-72">
              <label className="font-alliance mb-4 required">
                Charge Behaviour
              </label>
              <Select
                value={chargeBehavior}
                placeholder="Charge Behaviour"
                className="w-full ml-auto"
                onChange={(e) => setChargeBehaviour(e)}
              >
                {[
                  { id: 1, val: "prorate" },
                  { id: 2, val: "full" },
                ].map((behavior) => (
                  <Select.Option key={behavior.id} value={behavior.val}>
                    {behavior.val}
                  </Select.Option>
                ))}
              </Select>
            </div>
          </div>
        </div>
      </div>
    </Modal>
  );
};
export default RecurringChargesForm;
