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
  Switch,
} from "antd";
import "./UsageComponentForm.css";
import { Metrics } from "../../api/api";
import { MetricNameType, MetricType } from "../../types/metric-type";

const { Option } = Select;

type Props = {
  visible?: any;
  onCancel: () => void;
  componentsData: any;
  handleComponentAdd: (s: any) => void;
  editComponentItem: any;
  setEditComponentsItem: (s: any) => void;
};
function UsageComponentForm({
  handleComponentAdd,
  visible,
  onCancel,
  editComponentItem,
  setEditComponentsItem,
}: Props) {
  const [form] = Form.useForm();
  const [metrics, setMetrics] = useState<string[]>([]);
  const [isFree, setIsFree] = useState(true);
  const [isLimit, setIsLimit] = useState(false);
  const initalData = editComponentItem ?? {
    cost_per_batch: 0.0,
    metric_units_per_batch: 1,
    free_amount: 0,
  };

  useEffect(() => {
    Metrics.getMetrics().then((res) => {
      const data = res;
      if (data) {
        const metricList: string[] = [];
        for (let i = 0; i < data.length; i++) {
          if (typeof data[i].billable_metric_name !== undefined) {
            metricList.push(data[i].billable_metric_name as unknown as string);
          }
        }
        setMetrics(metricList);
      }
    });
  }, []);

  return (
    <Modal
      visible={visible}
      title="Create Component"
      okText="Create"
      okType="default"
      cancelText="Cancel"
      width={700}
      onCancel={() => {
        onCancel();
        form.resetFields();
        setEditComponentsItem(undefined);
      }}
      onOk={() => {
        form
          .validateFields()
          .then((values) => {
            handleComponentAdd(values);
            onCancel();
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
        initialValues={initalData}
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
            {metrics?.map((metric_name) => (
              <Option value={metric_name}>{metric_name}</Option>
            ))}
          </Select>
        </Form.Item>

        <div className="grid grid-cols-2 space-x-4 mt-4">
          <div>
            <div className="mb-4">
              Charge For This Metric?{" "}
              <Switch
                checkedChildren="YES"
                defaultChecked
                unCheckedChildren="NO"
                checked={!isFree}
                onChange={() => {
                  setIsFree(!isFree);
                  if (!isFree) {
                    form.setFieldsValue({
                      free_amount: 0,
                    });
                  }
                }}
              />
            </div>
            <div className=" space-x-4 mb-4">
              {!isFree && (
                <Form.Item name="free_amount" label="Free Units">
                  <InputNumber<string>
                    disabled={isFree}
                    defaultValue="0"
                    style={{
                      width: "100%",
                    }}
                    precision={5}
                    min="0"
                    step="0.00001"
                    stringMode
                  />
                </Form.Item>
              )}
            </div>
          </div>

          <div>
            <div className="mb-4">
              Does This Metric Have A Limit?{" "}
              <Switch
                checkedChildren="YES"
                defaultChecked
                unCheckedChildren="NO"
                checked={isLimit}
                onChange={() => {
                  setIsLimit(!isLimit);
                  if (isLimit) {
                    form.setFieldsValue({ max_metric_units: 0 });
                  }
                }}
              />
            </div>
            <div>
              {isLimit && (
                <Form.Item name="max_metric_units" label="Max Units">
                  <InputNumber<string>
                    disabled={!isLimit}
                    defaultValue="0"
                    style={{
                      width: "100%",
                    }}
                    precision={5}
                    min="0"
                    step="0.00001"
                    stringMode
                  />
                </Form.Item>
              )}
            </div>
          </div>
        </div>

        {isFree ? null : (
          <div>
            <p>Price per unit</p>
            <div className="grid grid-cols-2 space-x-4 mt-4">
              <div className="flex  align-middle">
                <Form.Item name="cost_per_batch" labelAlign="right">
                  <InputNumber addonBefore="$" defaultValue={0} precision={4} />
                </Form.Item>
                <p className="pt-1 px-2">Per</p>
                <Form.Item name="metric_units_per_batch">
                  <InputNumber<string>
                    addonAfter="units"
                    defaultValue="1"
                    precision={5}
                    min="0"
                    max="10"
                    step="0.00001"
                    stringMode
                  />
                </Form.Item>
              </div>
            </div>
          </div>
        )}
      </Form>
    </Modal>
  );
}

export default UsageComponentForm;
