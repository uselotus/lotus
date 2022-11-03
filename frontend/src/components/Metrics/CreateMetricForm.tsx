import { Modal, Form, Input, Select, Radio, Tooltip } from "antd";
import { MetricType } from "../../types/metric-type";
import React, { Fragment, useEffect, useState } from "react";
const { Option } = Select;

export interface CreateMetricState extends MetricType {
  title: string;
  aggregation_type_2: string;
  property_name_2: string;
}

const CreateMetricForm = (props: {
  state: CreateMetricState;
  visible: boolean;
  onSave: (state: CreateMetricState) => void;
  onCancel: () => void;
}) => {
  const [form] = Form.useForm();
  const [eventType, setEventType] = useState("");

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
          name="metric_type"
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
            prevValues.metric_type !== currentValues.metric_type
          }
        >
          {eventType === "aggregation" && (
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
                <Select defaultValue={"count"}>
                  <Option value="count">count</Option>
                  <Option value="unique">unique</Option>
                  <Option value="sum">sum</Option>
                  <Option value="max">max</Option>
                </Select>
              </Form.Item>
              <Form.Item
                noStyle
                shouldUpdate={(prevValues, currentValues) =>
                  prevValues.aggregation_type !==
                    currentValues.aggregation_type ||
                  prevValues.metric_type !== currentValues.metric_type
                }
              >
                {({ getFieldValue }) =>
                  getFieldValue("aggregation_type") === "sum" ||
                  getFieldValue("aggregation_type") === "max" ||
                  getFieldValue("aggregation_type") === "latest" ||
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
            </Fragment>
          )}
          {eventType === "stateful" && (
            <Fragment>
              <Form.Item
                name="aggregation_type_2"
                label="Aggregation Type"
                rules={[
                  {
                    required: true,
                    message: "Aggregation type is required",
                  },
                ]}
              >
                <Select defaultValue={"max"}>
                  <Option value="max">max</Option>
                  <Option value="latest">latest</Option>
                </Select>
              </Form.Item>
              <Form.Item
                name="property_name_2"
                label="Property Name"
                rules={[{ required: true }]}
              >
                <Input />
              </Form.Item>
              {/* <Form.Item
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
              </Form.Item> */}
            </Fragment>
          )}
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
