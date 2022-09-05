import React, { useEffect, useState } from "react";
import { Button, Form, Input, InputNumber, Modal, Radio, Select } from "antd";

const { Option } = Select;

function UsageComponentForm(props: { visible: boolean; onCancel: () => void }) {
  const [form] = Form.useForm();

  return (
    <Modal
      visible={props.visible}
      title="Add A Usage Pricing Component"
      okText="Create"
      okType="default"
      cancelText="Cancel"
      onCancel={props.onCancel}
      onOk={() => {
        form
          .validateFields()
          .then((values) => {
            console.log(values);
            form.submit();
          })
          .catch((info) => {
            console.log("Validate Failed:", info);
          });
      }}
    >
      <Form
        form={form}
        layout="vertical"
        name="component_form"
        initialValues={{
          cost_per_metric: 0.0,
          metric_amount_per_cost: 0.0,
          free_amount: 0,
        }}
      >
        <Form.Item
          name="metric"
          label="Metric"
          rules={[
            {
              required: true,
              message: "Please select a metric",
            },
          ]}
        >
          <Select>
            <Option value="test-runs">Test-Runs</Option>
          </Select>
        </Form.Item>
        <Form.Item name="cost_per_metric" label="Cost Per Unit Amount">
          <InputNumber addonBefore="$" defaultValue={0} precision={2} />
        </Form.Item>
        <Form.Item name="metric_amount_per_cost">
          <InputNumber addonBefore="per" defaultValue={1} precision={10} />
        </Form.Item>
        <Form.Item name="free_amount" label="Free Units">
          <InputNumber defaultValue={0} precision={5} />
        </Form.Item>
      </Form>
    </Modal>
  );
}

export default UsageComponentForm;
