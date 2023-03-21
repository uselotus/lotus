/* eslint-disable jsx-a11y/label-has-associated-control */
/* eslint-disable camelcase */
import React, { useState } from "react";
import { Button, Modal } from "antd";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plan } from "../../../api/api";

interface DeleteVersionModalProps {
  showModal: boolean;
  plan_id: string;
  version_id: string;
  setShowModal: (show: boolean) => void;
}

const DeleteVersionModal = ({
  showModal,
  setShowModal,
  version_id,
  plan_id,
}: DeleteVersionModalProps) => {
  const queryClient = useQueryClient();
  const [checked, setChecked] = useState(false);
  const mutation = useMutation(() => Plan.deletePlanVersion(version_id), {
    onSuccess: () => {
      queryClient.invalidateQueries(["plan_list"]);
      queryClient.invalidateQueries(["plan_subscriptions_get", version_id]);
      queryClient.invalidateQueries(["plan_detail", plan_id]);
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
            mutation.mutate();
            setShowModal(false);
          }}
          disabled={!checked}
          style={{ background: "#C3986B", borderColor: "#C3986B" }}
        >
          Confirm Delete
        </Button>,
      ]}
    >
      <div className="flex justify-center font-alliance items-center flex-col">
        <div className="mb-4">
          Are you sure you want to delete this version?
        </div>
        <div>
          <label className="mb-4 ml-4 required">I&apos;m sure</label>
          <input
            type="checkbox"
            name="check"
            id="check"
            checked={checked}
            onChange={() => setChecked(!checked)}
          />
        </div>
      </div>
    </Modal>
  );
};
export default DeleteVersionModal;
