import React, { useEffect, useState } from "react";
import {
  Button,
  Checkbox,
  Form,
  Input,
  InputNumber,
  Modal,
  Radio,
  Select,
} from "antd";
import "./UsageComponentForm.css";

const { Option } = Select;

function UsageComponentForm(props: {
  visible: boolean;
  onCancel: () => void;
  metrics: string[];
}) {
  const [form] = Form.useForm();
  const [isFree, setIsFree] = useState(false);
  const [isLimit, setIsLimit] = useState(false);

  return (
    <Modal
      visible={props.visible}
      title="Create Component"
      okText="Create"
      okType="default"
      cancelText="Cancel"
      width={600}
      onCancel={props.onCancel}
      onOk={() => {
        form
          .validateFields()
          .then((values) => {
            form.submit();
          })
          .catch((info) => {
            console.log("Validate Failed:", info);
          });
      }}
    >
      <Form
        form={form}
        layout="horizontal"
        name="component_form"
        initialValues={{
          cost_per_batch: 0.0,
          metric_units_per_batch: 1,
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
            {props.metrics.map((metric_name) => (
              <Option value={metric_name}>{metric_name}</Option>
            ))}
          </Select>
        </Form.Item>
        <div className="grid grid-cols-2 space-x-4">
          <Checkbox
            name="is_free"
            checked={isFree}
            onChange={() => setIsFree(!isFree)}
          >
            Charge For This Metric?
          </Checkbox>
          <Checkbox
            name="is_limit"
            checked={isLimit}
            onChange={() => setIsLimit(!isLimit)}
          >
            Does This Metric Have A Limit?
          </Checkbox>
        </div>
        <div className="grid grid-cols-2 space-x-4 my-5">
          <Form.Item name="free_amount" label="Free Units">
            <InputNumber defaultValue={0} precision={5} />
          </Form.Item>
          <Form.Item name="max_metric_units" label="Max Amount">
            <InputNumber defaultValue={0} precision={5} />
          </Form.Item>
        </div>
        <h3>Tiers</h3>
        <Form.Item name="cost_per_batch" label="Cost Per Unit Amount">
          <InputNumber addonBefore="$" defaultValue={0} precision={4} />
        </Form.Item>
        <Form.Item name="metric_units_per_batch">
          <InputNumber addonBefore="per" defaultValue={1} precision={5} />
        </Form.Item>
      </Form>
    </Modal>
  );
}

export default UsageComponentForm;
