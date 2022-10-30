import { Modal, Form, Input } from "antd";
import React from "react";

export interface CreateCustomerState {
  name: string;
  customer_id: string;
  title: string;
  subscriptions: string[];
  total_revenue_due: number;
}

const CreateCustomerForm = (props: {
  state: CreateCustomerState;
  visible: boolean;
  onSave: (state: CreateCustomerState) => void;
  onCancel: () => void;
}) => {
  const [form] = Form.useForm();

  form.setFieldsValue({
    name: props.state.name,
    customer_id: props.state.customer_id,
  });

  return (
    <Modal
      visible={props.visible}
      title={props.state.title}
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
          .catch((info) => {
            console.log("Validate Failed:", info);
          });
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
      </Form>
    </Modal>
  );
};

export default CreateCustomerForm;
