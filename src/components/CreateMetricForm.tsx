import { Modal, Form, Input, Select, Radio, Tooltip } from "antd";
import { MetricType } from "../types/metric-type";
import React, { Fragment, useState } from "react";
const { Option } = Select;

export interface CreateMetricState extends MetricType {
  title: string;
}

const CreateMetricForm = (props: {
  state: CreateMetricState;
  visible: boolean;
  onSave: (state: CreateMetricState) => void;
  onCancel: () => void;
}) => {
  const [form] = Form.useForm();
  const [eventType, setEventType] = useState("aggregation");
  const [statefulAggType, setStatefulAggType] = useState("max");

  form.setFieldsValue({
    event_name: props.state.event_name,
    property_name: props.state.property_name,
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
          name="event_name"
          label="Event Name"
          rules={[
            {
              required: true,
              message: "Please input the name of the event you want to track",
            },
          ]}
        >
          <Input />
        </Form.Item>
        <Form.Item
          name="event_type"
          label="Type"
          rules={[
            {
              required: true,
              message: "Metric type is required",
            },
          ]}
        >
          <Radio.Group
            optionType="button"
            buttonStyle="solid"
            value={eventType}
            defaultValue={eventType}
            onChange={(e) => {
              setEventType(e.target.value);
            }}
          >
            <Radio value="aggregation">Aggregation</Radio>
            <Radio value="stateful">Stateful</Radio>
          </Radio.Group>
        </Form.Item>
        <Form.Item
          noStyle
          shouldUpdate={(prevValues, currentValues) =>
            prevValues.event_type !== currentValues.event_type
          }
        >
          {({ getFieldValue }) =>
            getFieldValue("event_type") === "aggregation" ? (
              <Form.Item
                name="aggregation_type"
                label="Aggregation Type"
                rules={[
                  {
                    required: true,
                    message: "Aggregation type is required",
                  },
                ]}
              >
                <Select defaultValue={"count"}>
                  <Option value="count">count</Option>
                  <Option value="unique">unique</Option>
                  <Option value="sum">sum</Option>
                  <Option value="max">max</Option>
                </Select>
              </Form.Item>
            ) : (
              <Fragment>
                <Form.Item
                  name="aggregation_type"
                  label="Aggregation Type"
                  rules={[
                    {
                      required: true,
                      message: "Aggregation type is required",
                    },
                  ]}
                >
                  <Select
                    value={statefulAggType}
                    onChange={(e) => {
                      setStatefulAggType(e);
                    }}
                    defaultValue={statefulAggType}
                  >
                    <Option value="max">max</Option>
                    <Option value="last">last</Option>
                  </Select>
                </Form.Item>
                <Form.Item
                  name="stateful_aggregation_period"
                  label="Period"
                  rules={[
                    {
                      required: true,
                      message: "Period is required",
                    },
                  ]}
                >
                  <Select defaultValue={"day"}>
                    <Option value="day">day</Option>
                    <Option value="hour">hour</Option>
                  </Select>
                </Form.Item>
              </Fragment>
            )
          }
        </Form.Item>
        <Form.Item
          noStyle
          shouldUpdate={(prevValues, currentValues) =>
            prevValues.aggregation_type !== currentValues.aggregation_type ||
            prevValues.event_type !== currentValues.event_type
          }
        >
          {({ getFieldValue }) =>
            getFieldValue("aggregation_type") === "sum" ||
            getFieldValue("aggregation_type") === "max" ||
            getFieldValue("aggregation_type") === "last" ||
            getFieldValue("aggregation_type") == "unique" ? (
              <Form.Item
                name="property_name"
                label="Property Name"
                rules={[{ required: true }]}
              >
                <Input />
              </Form.Item>
            ) : null
          }
        </Form.Item>
        <Tooltip placement="left" title="Define a display name for this metric">
          <Form.Item
            name="billable_metric_name"
            label="Metric Name"
            rules={[
              {
                required: true,
                message: "Please define a unique name for this metric",
              },
            ]}
          >
            <Input />
          </Form.Item>
        </Tooltip>
      </Form>
    </Modal>
  );
};

export default CreateMetricForm;
