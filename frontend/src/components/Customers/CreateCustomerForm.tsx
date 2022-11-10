import { Modal, Form, Input, Select } from "antd";
import React from "react";

export interface CreateCustomerState {
  name: string;
  customer_id: string;
  title: string;
  subscriptions: string[];
  total_amount_due: number;
  email: string;
  payment_provider?: string;
  payment_provider_id?: string;
}

const CreateCustomerForm = (props: {
  visible: boolean;
  onSave: (state: CreateCustomerState) => void;
  onCancel: () => void;
}) => {
  const [form] = Form.useForm();

  return (
    <Modal
      visible={props.visible}
      title="Create a Customer"
      okText="Create"
      okType="default"
      cancelText="Cancel"
      onCancel={props.onCancel}
      onOk={() => {
        form
          .validateFields()
          .then((values) => {
            form.resetFields();
            props.onSave(values);
          })
          .catch((info) => {});
      }}
    >
      <Form form={form} layout="vertical" name="customer_form">
        <Form.Item
          name="name"
          label="Name"
          rules={[
            {
              required: true,
              message: "Please input the name of the customer",
            },
          ]}
        >
          <Input />
        </Form.Item>
        <Form.Item
          name="email"
          label="Email"
          rules={[
            {
              required: true,
              message: "Please input the email of the customer",
            },
          ]}
        >
          <Input />
        </Form.Item>
        <Form.Item
          name="customer_id"
          label="Customer ID"
          rules={[
            {
              required: true,
              message: "Unique customer_id is required",
            },
          ]}
        >
          <Input />
        </Form.Item>
        <div className="grid grid-cols-6 items-center gap-4">
          <Form.Item
            className="col-span-2"
            name="payment_provider"
            label="Payment Provider"
          >
            <Select options={[{ label: "Stripe", value: "stripe" }]} />
          </Form.Item>
          <Form.Item
            className="col-span-4"
            name="payment_provider_id"
            label="Payment Provider ID"
          >
            <Input />
          </Form.Item>
        </div>
      </Form>
    </Modal>
  );
};

export default CreateCustomerForm;
