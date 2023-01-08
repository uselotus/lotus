import React, { Fragment, useState } from "react";
import {
  Modal,
  Form,
  Input,
  Select,
  Radio,
  Tooltip,
  Switch,
  Collapse,
  Button,
  InputNumber,
} from "antd";
import { MetricType } from "../../types/metric-type";
import { render } from "react-dom";
import { MinusCircleOutlined, PlusOutlined } from "@ant-design/icons";
import AceEditor from "react-ace";
import "ace-builds/src-noconflict/mode-sql";
import "ace-builds/src-noconflict/theme-github";
const { Option } = Select;
const { Panel } = Collapse;

export interface CreateMetricState extends MetricType {
  title: string;
  usage_aggregation_type_2: string;
  property_name_2: string;
  granularity_2?: string;
  filters?: {
    property_name: string;
    operator: string;
    comparison_value: string;
  }[];
}

const CreateMetricForm = (props: {
  state: CreateMetricState;
  visible: boolean;
  onSave: (state: CreateMetricState) => void;
  onCancel: () => void;
}) => {
  const [form] = Form.useForm();
  const statefulGranularity = Form.useWatch("granularity_2", form);
  const [eventType, setEventType] = useState("counter");
  const [rate, setRate] = useState(false);
  const [preset, setPreset] = useState("none");
  const [filters, setFilters] = useState();
  const [customSQL, setCustomSQL] = useState<null | string>();

  // useEffect(() => {
  //   if (props.visible === false) {
  //     form.resetFields();
  //   }
  // }, [props.visible]);

  const [costMetric, setCostMetric] = useState(false);

  const changeFormPreset = (preset: string) => {
    switch (preset) {
      case "none":
        setEventType("counter");
        setRate(false);

        form.resetFields();
        break;
      case "seats":
        setEventType("stateful");
        setRate(false);
        setCostMetric(false);

        form.setFieldsValue({
          aggregation_type_2: "max",
          event_name: "seats",
          metric_type: "stateful",
          property_name_2: "seat_count",
          granularity_2: "total",
          metric_name: "Seats",
          event_type: "total",
        });
        break;
      case "calls":
        setEventType("counter");
        setRate(false);
        setCostMetric(false);

        form.setFieldsValue({
          usage_aggregation_type: "count",
          metric_name: "API Post Calls",
          event_name: "api_post",
          metric_type: "counter",
        });
        break;
      case "rate":
        setEventType("counter");
        setRate(true);
        setCostMetric(false);

        form.setFieldsValue({
          usage_aggregation_type: "sum",
          metric_name: "Database Insert Rate",
          event_name: "db_insert",
          metric_type: "counter",
          property_name: "#_of_inserts",
          rate: true,
          billable_aggregation_type: "max",
          granularity: "minutes",
        });
    }
  };

  return (
    <Modal
      visible={props.visible}
      title={props.state.title}
      okText="Create"
      okType="primary"
      cancelText="Cancel"
      width={800}
      onCancel={props.onCancel}
      onOk={() => {
        form
          .validateFields()
          .then((values) => {
            values.is_cost_metric = costMetric;
            if (rate) {
              values.metric_type = "rate";
            }
            if (values.metric_type === "custom") {
              values.custom_sql = customSQL;
            }
            props.onSave(values);
            form.resetFields();
            setRate(false);
            setEventType("counter");
            setPreset("none");
          })
          .catch((info) => {});
      }}
    >
      <div className="grid grid-cols-8 my-4 gap-4 items-center">
        <h3 className="col-span-2">Templates</h3>
        <Radio.Group
          buttonStyle="solid"
          optionType="button"
          className="col-span-6 space-x-4"
          value={preset}
          onChange={(e) => {
            setPreset(e.target.value);
            changeFormPreset(e.target.value);
          }}
        >
          <Radio value="none">No Template</Radio>
          <Radio value="seats">Seats</Radio>
          <Radio value="calls">API Calls</Radio>
          <Radio value="rate">Insert Rate</Radio>
        </Radio.Group>
      </div>
      <div className="seperator" />
      <Form
        form={form}
        layout="vertical"
        name="customer_form"
        initialValues={{
          metric_type: "counter",
          usage_aggregation_type: "count",
          usage_aggregation_type_2: "max",
          granularity_2: "days",
          event_type: "total",
        }}
      >
        <div className="grid grid-cols-2 gap-4">
          <Tooltip
            placement="left"
            title="Define a display name for this metric"
          >
            <Form.Item
              name="metric_name"
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
        </div>

        <div className="grid grid-cols-2 gap-4">
          <Form.Item
            name="metric_type"
            className="justify-center"
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
                if (e.target.value === "counter") {
                  setRate(false);
                }
              }}
            >
              <Radio value="counter">Counter</Radio>
              <Radio value="stateful">Gauge</Radio>
              {/* <Radio value="custom">Custom</Radio> */}
            </Radio.Group>
          </Form.Item>
          <Form.Item label="Does this metric represent a cost?">
            <Switch
              checked={costMetric}
              onChange={() => {
                setCostMetric(!costMetric);
                if (!costMetric) {
                  form.setFieldsValue({
                    is_cost_metric: false,
                  });
                } else {
                  form.setFieldsValue({
                    is_cost_metric: true,
                  });
                }
              }}
            />
          </Form.Item>
        </div>
        <Form.Item
          noStyle
          shouldUpdate={(prevValues, currentValues) =>
            prevValues.metric_type !== currentValues.metric_type
          }
        >
          {eventType === "counter" && (
            <Fragment>
              <Form.Item
                name="usage_aggregation_type"
                label="Aggregation Type"
                rules={[
                  {
                    required: true,
                    message: "Aggregation type is required",
                  },
                  //if rate is selected, don't allow unique
                  {
                    validator: (_, value) => {
                      if (rate && value === "unique") {
                        return Promise.reject(
                          new Error("Cannot use unique with rate")
                        );
                      }
                      return Promise.resolve();
                    },
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
                  prevValues.usage_aggregation_type !==
                    currentValues.usage_aggregation_type ||
                  prevValues.metric_type !== currentValues.metric_type
                }
              >
                {({ getFieldValue }) =>
                  getFieldValue("usage_aggregation_type") === "sum" ||
                  getFieldValue("usage_aggregation_type") === "max" ||
                  getFieldValue("usage_aggregation_type") === "unique" ? (
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
              <div className="mb-5">
                <h4>
                  Add Rate. This will allow you to track the metric over windows
                  of time.
                </h4>
                <Switch
                  checked={rate}
                  onChange={() => {
                    setRate(!rate);
                    if (!rate) {
                      form.setFieldsValue({
                        billable_aggregation_type: "max",
                        granularity: "days",
                      });
                    } else {
                      form.setFieldsValue({
                        metric_type: "counter",
                      });
                    }
                  }}
                  // disabled={
                  //   form.getFieldValue("usage_aggregation_type") !== "unique"
                  // }
                />
              </div>

              {rate && (
                <Fragment>
                  <Form.Item
                    name="granularity"
                    label="Rate Period"
                    rules={[
                      {
                        required: true,
                        message: "Period is required",
                      },
                    ]}
                  >
                    <Select defaultValue="minutes">
                      <Option value="minutes">minute</Option>

                      <Option value="hours">hour</Option>

                      <Option value="days">day</Option>

                      <Option value="months">month</Option>
                    </Select>
                  </Form.Item>
                  <Form.Item
                    name="billable_aggregation_type"
                    label="Rate Aggregation Type"
                    rules={[
                      {
                        required: true,
                        message: "Aggregation type is required",
                      },
                    ]}
                  >
                    <Select defaultValue={"max"}>
                      <Option value="max">max</Option>
                    </Select>
                  </Form.Item>
                </Fragment>
              )}
            </Fragment>
          )}
          {eventType === "stateful" && (
            <Fragment>
              <div className="grid grid-cols-2 gap-4">
                <Form.Item
                  name="usage_aggregation_type_2"
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
                  </Select>
                </Form.Item>
                <Form.Item
                  name="event_type"
                  label="Event Type (how the property amount is reported)"
                  rules={[{ required: true }]}
                >
                  <Select defaultValue={"total"}>
                    <Option value="total">total</Option>
                    <Option value="delta">delta</Option>
                  </Select>
                </Form.Item>
              </div>

              <Form.Item
                name="property_name_2"
                label="Property Name"
                rules={[{ required: true }]}
              >
                <Input />
              </Form.Item>
              <Form.Item name="granularity_2" label="Proration">
                <Select>
                  <Option value="minutes">minute</Option>
                  <Option value="hours">hour</Option>
                  <Option value="days">day</Option>
                  <Option value="months">month</Option>
                  <Option value="quarters">quarter</Option>
                  <Option value="years">year</Option>
                  <Option value="total">none</Option>
                </Select>
              </Form.Item>

              {/* {statefulGranularity && statefulGranularity !== "total" && (
                <p className=" text-darkgold mb-4">
                  When inputting the price for this metric, you will be inputing
                  the price per {statefulGranularity.slice(0, -1)}
                </p>
              )} */}
            </Fragment>
          )}
        </Form.Item>
        {eventType === "custom" && (
          <AceEditor
            mode="sql"
            theme="github"
            onChange={(newValue) => setCustomSQL(newValue)}
            value={customSQL ? customSQL : ""}
            editorProps={{ $blockScrolling: true }}
            setOptions={{
              enableBasicAutocompletion: true,
              enableLiveAutocompletion: true,
              enableSnippets: true,
              showLineNumbers: true,
              tabSize: 2,
            }}
          />
        )}

        {eventType !== "custom" && (
          <Collapse>
            <Panel header="Filters" key="1">
              <Form.List name="filters">
                {(fields, { add, remove }, { errors }) => (
                  <>
                    {fields.map((field, index) => (
                      <Form.Item
                        required={false}
                        key={field.key}
                        label={index === 0 ? "" : "and"}
                        className="mt-4"
                      >
                        <div className="flex flex-col space-y-4">
                          <Form.Item
                            {...field}
                            name={[field.name, "property_name"]}
                            validateTrigger={["onChange", "onBlur"]}
                            rules={[
                              {
                                required: true,
                                whitespace: true,
                                message:
                                  "Please input a property name name or delete this filter.",
                              },
                            ]}
                            noStyle
                          >
                            <Input
                              placeholder="property name"
                              style={{ width: "30%" }}
                            />
                          </Form.Item>
                          <Form.Item
                            name={[field.name, "operator"]}
                            rules={[
                              {
                                required: true,
                                whitespace: true,
                                message:
                                  "Please input a property name name or delete this filter.",
                              },
                            ]}
                          >
                            <Select style={{ width: "50%" }}>
                              <Option value="isin">is (string)</Option>
                              <Option value="isnotin">is not (string)</Option>
                              <Option value="eq">= </Option>
                              <Option value="gte">&#8805;</Option>
                              <Option value="gt"> &#62; </Option>
                              <Option value="lt"> &#60;</Option>
                              <Option value="lte">&#8804;</Option>
                            </Select>
                          </Form.Item>

                          <div className="grid grid-cols-2 w-6/12">
                            <Form.Item
                              name={[field.name, "comparison_value"]}
                              style={{ alignSelf: "middle" }}
                            >
                              <Input />
                            </Form.Item>
                            {fields.length > 0 ? (
                              <MinusCircleOutlined
                                className="hover:bg-background place-self-center p-4"
                                onClick={() => remove(field.name)}
                              />
                            ) : null}
                          </div>
                        </div>
                      </Form.Item>
                    ))}
                    <Form.Item>
                      <Button
                        type="dashed"
                        onClick={() => add()}
                        style={{ width: "60%" }}
                        icon={<PlusOutlined />}
                      >
                        Add filter
                      </Button>
                      <Form.ErrorList errors={errors} />
                    </Form.Item>
                  </>
                )}
              </Form.List>
            </Panel>
          </Collapse>
        )}
      </Form>
    </Modal>
  );
};

export default CreateMetricForm;
