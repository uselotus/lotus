/* eslint-disable jsx-a11y/label-has-associated-control */
/* eslint-disable camelcase */
import React, { useState } from "react";
import { Button, Modal } from "antd";
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Plan } from "../../../api/api";
import { components } from "../../../gen-types";
import PricingUnitDropDown from "../../PricingUnitDropDown";

interface AddCurrencyModalProps {
  showModal: boolean;
  version: number;
  setShowModal: (show: boolean) => void;
  plan_id: string;
  version_id: string;
}
type BodyType = components["schemas"]["InitialPlanVersionCreateRequest"] & {
  plan_id: string;
};

const AddCurrencyModal = ({
  showModal,
  setShowModal,
  plan_id,
  version,
  version_id,
}: AddCurrencyModalProps) => {
  const queryClient = useQueryClient();
  const [currency, setCurrency] = useState("");
  const mutation = useMutation((body: BodyType) => Plan.createVersion(body), {
    onSuccess: () => {
      queryClient.invalidateQueries(["plan_list"]);
      queryClient.invalidateQueries(["plan_detail", plan_id]);
      queryClient.invalidateQueries(["plan_subscriptions_get", version_id]);
    },
  });
  return (
    <Modal
      title="Add Currency"
      visible={showModal}
      onCancel={() => setShowModal(false)}
      footer={[
        <Button
          key="back"
          onClick={() => setShowModal(false)}
          style={{ background: "#F5F5F5", borderColor: "#F5F5F5" }}
        >
          Cancel
        </Button>,
        <Button
          key="submit"
          type="primary"
          onClick={() => {
            mutation.mutate({ currency_code: currency, version, plan_id });
            setShowModal(false);
          }}
          disabled={currency.length < 1}
          style={{ background: "#C3986B", borderColor: "#C3986B" }}
        >
          Add Currency
        </Button>,
      ]}
    >
      <div className="flex justify-center items-center flex-col">
        <label className="mb-4 required">Add Currency</label>
        <PricingUnitDropDown
          size="middle"
          className="w-1/4"
          setCurrentCurrency={(currencyValue) => setCurrency(currencyValue)}
        />
      </div>
    </Modal>
  );
};
export default AddCurrencyModal;
