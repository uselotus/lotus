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
  const [isCharge, setIsCharge] = useState(
    editComponentItem?.free_metric_units !== undefined ? true : false
  );
  const [isLimit, setIsLimit] = useState(
    editComponentItem?.max_metric_units ? true : false
  );
  const initalData = editComponentItem ?? null;

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
      okButtonProps={{
        className: "bg-black text-white justify-self-end",
      }}
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

            form.submit();
          })
          .catch((info) => {});
      }}
    >
      <Form
        form={form}
        layout="vertical"
        name="component_form"
        initialValues={initalData}
      >
        <div className="grid grid-cols-12 space-x-4 mt-4">
          <p className="col-span-1 pt-1">Metric:</p>

          <Form.Item
            className="col-span-11"
            name="metric"
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
        </div>

        <div className="grid grid-cols-2 space-x-4 mt-4">
          <div>
            <div className="mb-4">
              Charge For This Metric?{" "}
              <Switch
                checkedChildren="YES"
                unCheckedChildren="NO"
                checked={isCharge}
                onChange={() => {
                  setIsCharge(!isCharge);
                  if (!isCharge) {
                    form.setFieldsValue({
                      free_metric_units: 0,
                      cost_per_batch: 0,
                      metric_units_per_batch: 1,
                    });
                  } else {
                    form.setFieldsValue({
                      free_metric_units: undefined,
                      cost_per_batch: undefined,
                      metric_units_per_batch: undefined,
                    });
                  }
                }}
              />
            </div>
            <div className=" space-x-4 mb-4">
              {isCharge && (
                <Form.Item name="free_metric_units" label="Free Units">
                  <InputNumber<string>
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
                unCheckedChildren="NO"
                checked={isLimit}
                onChange={() => {
                  setIsLimit(!isLimit);
                  if (!isLimit) {
                    form.setFieldsValue({
                      max_metric_units: 1,
                    });
                  }
                }}
              />
            </div>
            <div>
              {isLimit && (
                <Form.Item name="max_metric_units" label="Max Units">
                  <InputNumber<string>
                    disabled={!isLimit}
                    defaultValue="1"
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

        {isCharge ? (
          <div>
            <p>Price per unit</p>
            <div className="grid grid-cols-2 space-x-4 mt-4">
              <div className="flex align-middle">
                <Form.Item name="cost_per_batch" labelAlign="right">
                  <InputNumber addonBefore="$" defaultValue={0} precision={4} />
                </Form.Item>
                <p className="px-2">Per</p>
                <Form.Item name="metric_units_per_batch">
                  <InputNumber<string>
                    addonAfter="units"
                    defaultValue="1"
                    precision={5}
                    min="0"
                    step="0.00001"
                    stringMode
                  />
                </Form.Item>
              </div>
            </div>
          </div>
        ) : null}
      </Form>
    </Modal>
  );
}

export default UsageComponentForm;
