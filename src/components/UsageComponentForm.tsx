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
  const [isFree, setIsFree] = useState(true);
  const [isLimit, setIsLimit] = useState(false);

  return (
    <Modal
      visible={props.visible}
      title="Create Component"
      okText="Create"
      okType="default"
      cancelText="Cancel"
      width={700}
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
        className="usage-form1"
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
        <div className="grid grid-cols-2 space-x-4 my-4">
          <Checkbox
            name="is_free"
            checked={!isFree}
            onChange={() => {
              setIsFree(!isFree);
              if (!isFree) {
                form.setFieldsValue({
                  free_amount: 0,
                });
              }
            }}
          >
            Charge For This Metric?
          </Checkbox>
          <Checkbox
            name="is_limit"
            checked={isLimit}
            onChange={() => {
              setIsLimit(!isLimit);
              if (isLimit) {
                form.setFieldsValue({ max_metric_units: 0 });
              }
            }}
          >
            Does This Metric Have A Limit?
          </Checkbox>
        </div>
        <div className="grid grid-cols-2 space-x-4 my-5">
          <Form.Item name="free_amount" label="Free Units">
            <InputNumber defaultValue={0} precision={5} disabled={isFree} />
          </Form.Item>
          <Form.Item name="max_metric_units" label="Max Amount">
            <InputNumber precision={5} disabled={!isLimit} />
          </Form.Item>
        </div>
        {isFree ? null : (
          <div>
            <div className=" bg-grey3 mx-2 my-5">
              <h3 className="py-2 px-3">Tiers</h3>
            </div>
            <div className="flex flex-row items-center space-x-2">
              <p>From</p>
              <Form.Item name="free_amount">
                <InputNumber
                  defaultValue={0}
                  precision={4}
                  value={form.getFieldValue("free_amount")}
                />
              </Form.Item>
              <p>To</p>
              <Form.Item name="max_metric_units">
                <InputNumber
                  defaultValue={0}
                  precision={4}
                  disabled={!isLimit}
                  value={form.getFieldValue("max_metric_units")}
                />
              </Form.Item>
              <p>, $</p>
              <Form.Item name="cost_per_batch">
                <InputNumber defaultValue={0} precision={4} />
              </Form.Item>
              <p>Per</p>
              <Form.Item name="metric_units_per_batch">
                <InputNumber defaultValue={1} precision={5} />
              </Form.Item>
              <p>Units</p>
            </div>
          </div>
        )}
      </Form>
    </Modal>
  );
}

export default UsageComponentForm;
