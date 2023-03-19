/* eslint-disable no-plusplus */
/* eslint-disable react/no-array-index-key */
/* eslint-disable no-shadow */
/* eslint-disable use-isnan */
import React, { useRef, useState, useEffect } from "react";
import { useQuery, UseQueryResult, useQueryClient } from "react-query";
import { EventPages } from "../../types/event-type";
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
  Tag,
  InputNumber,
} from "antd";
import {
  CreateMetricType,
  MetricCategory,
  EventType,
  TimePeriodType,
  TimePeriods,
  CategoricalFilterType,
  NumericFilterType,
} from "../../types/metric-type";
import { MinusCircleOutlined, PlusOutlined } from "@ant-design/icons";
import AceEditor from "react-ace";
import "ace-builds/src-noconflict/mode-sql";
import "ace-builds/src-noconflict/theme-github";
import "ace-builds/src-noconflict/ext-language_tools";
import { format } from "sql-formatter";
import { Events } from "../../api/api";

const { Option } = Select;
const { Panel } = Collapse;

function CreateMetricForm(props: {
  state: CreateMetricType;
  visible: boolean;
  onSave: (state: CreateMetricType) => void;
  onCancel: () => void;
}) {
  const [form] = Form.useForm();
  const [eventType, setEventType] = useState("counter");
  const [propertyNames, setPropertyNames] = useState<[string]>([]);
  const [preset, setPreset] = useState("none");
  const errorMessages = useRef([]);
  const [errors, setErrors] = useState<string[]>();
  const [showTags, setShowTags] = useState({});
  type MixedFilterType = CategoricalFilterType | NumericFilterType;
  const [filters, setFilters] = useState<MixedFilterType[]>([]);
  const [expandForm, setExpandForm] = useState(false);
  const [customSQL, setCustomSQL] = useState<null | string>(
    "SELECT COUNT(*) as usage_qty FROM events"
  );
  const [selectedGranularity, setSelectedGranularity] =
    useState<TimePeriodType | null>(null);
  const [selectedProration, setSelectedProration] =
    useState<TimePeriodType | null>(null);

  const { data, isLoading }: UseQueryResult<EventPages> = useQuery<EventPages>(
    ["preview events"],
    () => Events.searchEventNames(true).then((res) => res)
  );

  const disableOption = (option: TimePeriodType) => {
    if (selectedGranularity) {
      if (selectedGranularity === "total") {
        return false;
      } else {
        const granularityIndex = TimePeriods.indexOf(selectedGranularity);
        const optionIndex = TimePeriods.indexOf(option);
        return optionIndex >= granularityIndex && option !== "total";
      }
    }
  };

  const formatSQL = () => {
    if (customSQL) {
      // format the SQL code
      const formattedSQL = format(customSQL, {
        language: "postgresql",
      });
      setCustomSQL(formattedSQL);
    }
  };

  const getGaugeGranularityRules = () => {
    if (eventType === "gauge") {
      return [{ required: true, message: "Period is required" }];
    } else {
      return [];
    }
  };

  const getRateGranularityRules = () => {
    if (eventType === "rate") {
      return [{ required: true, message: "Period is required" }];
    } else {
      return [];
    }
  };

  const handleGranularityChange = (value: TimePeriodType) => {
    setSelectedGranularity(value);
    setSelectedProration("total");
    form.setFieldsValue({ gauge_granularity: value });
  };

  const handleProrationChange = (value: TimePeriodType) => {
    setSelectedProration(value);
    form.setFieldsValue({ proration: value });
  };

  const [costMetric, setCostMetric] = useState(false);

  const handleCreateMetricTypeChange = (createMetricType: MetricCategory) => {
    setEventType(createMetricType);
    form.setFieldsValue({
      usage_aggregation_type: "",
      billable_aggregation_type: "",
      event_type: "",
      property_name: "",
      gauge_granularity: "",
      rate_granularity: "",
    });
    setSelectedGranularity(null);
    setSelectedProration("total");
    if (createMetricType === "custom") {
      // Set the value of the event_name form field to an empty string
      form.setFieldsValue({
        event_name: "",
      });
    }
  };

  const changeFormPreset = (preset: string) => {
    switch (preset) {
      case "none":
        handleCreateMetricTypeChange("counter");

        form.resetFields();
        break;
      case "seats":
        handleCreateMetricTypeChange("gauge");
        setCostMetric(false);

        form.setFieldsValue({
          event_name: "seats",
          metric_type: "gauge",
          property_name: "seat_count",
          gauge_granularity: "months",
          metric_name: "Seats",
          event_type: "delta",
          proration: "total",
        });
        setSelectedGranularity("months");
        setSelectedProration("total");
        break;
      case "calls":
        handleCreateMetricTypeChange("counter");
        setCostMetric(false);

        form.setFieldsValue({
          usage_aggregation_type: "count",
          metric_name: "API Post Calls",
          event_name: "api_post",
          metric_type: "counter",
        });
        break;
      case "rate":
        handleCreateMetricTypeChange("rate");
        setCostMetric(false);

        form.setFieldsValue({
          usage_aggregation_type: "sum",
          metric_name: "Database Insert Rate",
          event_name: "db_insert",
          metric_type: "rate",
          property_name: "num_inserts",
          billable_aggregation_type: "max",
          rate_granularity: "minutes",
        });
        break;
      default:
        break;
    }
  };

  return (
    <Modal
      visible={props.visible}
      title="Create Metric"
      okText="Create"
      okType="primary"
      okButtonProps={{
        id: "Create-metric-button",
      }}
      cancelText="Cancel"
      width={800}
      onCancel={props.onCancel}
      onOk={() => {
        form.validateFields().then((values) => {
          var { filters } = values;
          filters = filters || [];
          filters.forEach((filter) => {
            if (
              (filter.operator === "isin" || filter.operator === "isnotin") &&
              !filter.comparison_value.some((el) => Number(el) >= 0 === true)
            ) {
              errorMessages.current = [];
            } else if (
              (filter.operator !== "isin" || filter.operator !== "isnotin") &&
              Number(filter.comparison_value) >= 0
            ) {
              errorMessages.current = [];
            } else if (
              (filter.operator !== "isin" || filter.operator !== "isnotin") &&
              Number(filter.comparison_value) < 0 === false
            ) {
              errorMessages.current = errorMessages.current.concat([
                `${filter.operator} requires number conversion type`,
              ]);
            } else if (
              (filter.operator === "isin" || filter.operator === "isnotin") &&
              filter.comparison_value.every((el) => Number(el) >= 0 === false)
            ) {
              errorMessages.current = [];
            }
          });
          setErrors(errorMessages.current);
          if (errorMessages.current.length) {
            return;
          }

          if (Array.isArray(values.event_name)) {
            values.event_name = values.event_name[0];
          }
          if (Array.isArray(values.property_name)) {
            values.property_name = values.property_name[0];
          }

          const numericFilters: NumericFilterType[] = [];
          const categoricalFilters: CategoricalFilterType[] = [];
          if (values.filters && values.filters.length > 0) {
            for (let i = 0; i < values.filters.length; i++) {
              const comparisonValue = values.filters[i].comparison_value;
              if (["isin", "isnotin"].includes(values.filters[i].operator)) {
                //comparisonValue will be a list of strings
                categoricalFilters.push({
                  property_name: values.filters[i].property_name,
                  operator: values.filters[i].operator,
                  comparison_value: [...values.filters[i].comparison_value],
                });
              } else {
                numericFilters.push({
                  property_name: values.filters[i].property_name,
                  operator: values.filters[i].operator,
                  comparison_value: parseFloat(
                    values.filters[i].comparison_value
                  ),
                });
              }
            }
          }
          if (values.metric_type === "custom" && customSQL) {
            values.custom_sql = format(customSQL, {
              language: "postgresql",
            });
          }

          var newMetric: CreateMetricType;
          if (values.metric_type === "counter") {
            newMetric = {
              event_name: values.event_name,
              usage_aggregation_type: values.usage_aggregation_type,
              metric_type: "counter",
              metric_name: values.metric_name,
              numeric_filters: numericFilters,
              categorical_filters: categoricalFilters,
              is_cost_metric: values.is_cost_metric,
              ...(values.property_name
                ? { property_name: values.property_name }
                : {}),
            };
          } else if (values.metric_type === "gauge") {
            newMetric = {
              event_name: values.event_name,
              property_name: values.property_name,
              usage_aggregation_type: "max",
              metric_type: "gauge",
              metric_name: values.metric_name,
              event_type: values.event_type,
              numeric_filters: numericFilters,
              categorical_filters: categoricalFilters,
              granularity: values.gauge_granularity,
              proration: values.proration,
              is_cost_metric: false,
            };
          } else if (values.metric_type === "rate") {
            newMetric = {
              event_name: values.event_name,
              metric_name: values.metric_name,
              usage_aggregation_type: values.usage_aggregation_type,
              granularity: values.rate_granularity,
              metric_type: "rate",
              billable_aggregation_type: "max",
              numeric_filters: numericFilters,
              categorical_filters: categoricalFilters,
              ...(values.property_name
                ? { property_name: values.property_name }
                : {}),
              is_cost_metric: false,
            };
          } else {
            newMetric = {
              metric_name: values.metric_name,
              metric_type: "custom",
              custom_sql: values.custom_sql,
              is_cost_metric: false,
              numeric_filters: [],
              categorical_filters: [],
            };
          }
          props.onSave(newMetric);
          setCustomSQL("SELECT COUNT(*) as usage_qty FROM events");
          form.resetFields();
          setEventType("counter");
          setPreset("none");
          setExpandForm(false);
        });

        // form.validateFields().then((values) => {

        // });
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
          <Radio value="rate">DB Insert Rate</Radio>
        </Radio.Group>
      </div>

      <div className="text-center mb-6 mt-6">
        <span className="bg-white px-3 text-gray-500 font-bold relative z-10">
          or
        </span>
        <hr className="border-gray-300 border-1 mt-2" />
      </div>

      {(!expandForm || preset === "none") && (
        <div className="flex justify-center items-center mt-8 mb-8">
          <Button
            type="default"
            id="define-new-metric"
            onClick={() => {
              setExpandForm(true);
            }}
          >
            Define a new metric
          </Button>
        </div>
      )}

      <Form
        form={form}
        layout="vertical"
        name="metric_form"
        initialValues={{
          metric_type: "counter",
          usage_aggregation_type: "count",
          billable_aggregation_type: "max",
          granularity: "days",
          event_type: "total",
        }}
      >
        {(expandForm || preset !== "none") && (
          <div>
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
                  <Input id="metric-name-input" />
                </Form.Item>
              </Tooltip>
              {eventType !== "custom" && (
                <Tooltip
                  placement="left"
                  title="Define the name of the event you want to track"
                >
                  <Form.Item
                    name="event_name"
                    label="Event Name"
                    rules={[
                      {
                        required: true,
                        message:
                          "Please input the name of the event you want to track",
                      },
                    ]}
                  >
                    <Select
                      mode="tags"
                      placeholder="Start typing to look up matching events"
                      id="event-name-input"
                      onChange={(event_name: string) => {
                        const selectedEvent = data?.results?.find(
                          (e) => e.event_name == event_name
                        );
                        const temp = Object.keys(selectedEvent?.properties).map(
                          (key) => key
                        );
                        setPropertyNames(temp);
                      }}
                    >
                      {data?.results?.map((e) => (
                        <Option value={e.event_name}>{e.event_name}</Option>
                      ))}
                    </Select>
                  </Form.Item>
                </Tooltip>
              )}
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
                    handleCreateMetricTypeChange(e.target.value);
                    setPreset("none");
                  }}
                >
                  <Radio value="counter">Counter</Radio>
                  <Radio value="gauge">Gauge</Radio>
                  <Radio value="rate">Rate</Radio>
                  <Radio value="custom">Custom (Beta)</Radio>
                </Radio.Group>
              </Form.Item>
            </div>
            <Form.Item
              noStyle
              shouldUpdate={(prevValues, currentValues) =>
                prevValues.metric_type !== currentValues.metric_type
              }
            >
              {(eventType === "counter" || eventType === "rate") && (
                <>
                  <Form.Item
                    name="usage_aggregation_type"
                    label="Aggregation Type"
                    rules={[
                      {
                        required: true,
                        message: "Aggregation type is required",
                      },
                      // if rate is selected, don't allow unique
                      {
                        validator: (_, value) => {
                          if (eventType == "rate" && value === "unique") {
                            return Promise.reject(
                              new Error("Cannot use unique with rate")
                            );
                          }
                          return Promise.resolve();
                        },
                      },
                    ]}
                  >
                    <Select defaultValue="count">
                      <Option value="count">count</Option>
                      {eventType === "counter" && (
                        <Option value="unique">unique</Option>
                      )}
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
                          rules={[
                            {
                              validator: (rule, value) => {
                                if (value && value.length > 0) {
                                  return Promise.resolve();
                                }
                                return Promise.reject(
                                  "Please select a property name"
                                );
                              },
                            },
                          ]}
                        >
                          <Select
                            mode="tags"
                            maxTagCount={1}
                            placeholder="Start typing to look up matching property names"
                          >
                            {propertyNames.map((p) => (
                              <Option value={p}>{p}</Option>
                            ))}
                          </Select>
                        </Form.Item>
                      ) : null
                    }
                  </Form.Item>

                  {eventType === "rate" && (
                    <>
                      <Form.Item
                        name="rate_granularity"
                        label="Rate Period"
                        rules={getRateGranularityRules()}
                      >
                        <Select>
                          <Option value="minutes">minute</Option>

                          <Option value="hours">hour</Option>

                          <Option value="days">day</Option>

                          <Option value="months">month</Option>
                        </Select>
                      </Form.Item>
                    </>
                  )}
                </>
              )}
              {eventType === "gauge" && (
                <>
                  <div className="grid grid-cols-2 gap-4">
                    <Form.Item
                      name="event_type"
                      label="Event Type (how the property amount is reported)"
                      rules={[{ required: true }]}
                    >
                      <Select>
                        <Option value="total">total</Option>
                        <Option value="delta">delta</Option>
                      </Select>
                    </Form.Item>
                  </div>

                  <Form.Item
                    name="property_name"
                    label="Property Name"
                    rules={[{ required: true }]}
                  >
                    <Select
                      mode="tags"
                      maxTagCount={1}
                      placeholder="Start typing to look up matching property names"
                    >
                      {propertyNames.map((p) => (
                        <Option value={p}>{p}</Option>
                      ))}
                    </Select>
                  </Form.Item>

                  <Form.Item
                    name="gauge_granularity"
                    label="Unit Defined Per"
                    rules={getGaugeGranularityRules()}
                  >
                    <Tooltip
                      placement="left"
                      title="Define the unit of measurement for this gauge metric. This would be `hours` for AWS-style CPU-hour metrics, or `month` for a monthly metric based on seats/users."
                    >
                      <Select
                        value={selectedGranularity}
                        onChange={handleGranularityChange}
                      >
                        <Select.Option value="seconds">second</Select.Option>
                        <Select.Option value="minutes">minute</Select.Option>
                        <Select.Option value="hours">hour</Select.Option>
                        <Select.Option value="days">day</Select.Option>
                        <Select.Option value="months">month</Select.Option>
                        <Select.Option value="total">
                          plan duration
                        </Select.Option>
                      </Select>
                    </Tooltip>
                  </Form.Item>
                </>
              )}
            </Form.Item>
            {eventType === "custom" && (
              <div>
                <p>
                  The query you're building should calculate the raw usage
                  number for a customer's subscription. You'll define the price
                  of the accumulated usage later. You'll have access to a table
                  called <Tag>events</Tag>containing all of the events for the
                  customer whose subscription usage you're calculating. Each row
                  represents an event and has the following columns available:
                </p>
                <h4>
                  <Tag>
                    event_name (
                    <a href="https://www.postgresql.org/docs/current/datatype-character.html">
                      string
                    </a>
                    )
                  </Tag>{" "}
                  the name of the event.
                </h4>
                <h4>
                  <Tag>
                    properties (
                    <a href="https://www.postgresql.org/docs/current/datatype-json.html">
                      jsonb
                    </a>
                    )
                  </Tag>{" "}
                  the properties you specified when you sent the event.
                </h4>
                <h4>
                  <Tag>
                    time_created (
                    <a href="https://www.postgresql.org/docs/current/datatype-datetime.html">
                      timestamptz
                    </a>
                    )
                  </Tag>{" "}
                  the time the event happened.
                </h4>
                <h4>
                  <Tag>
                    start_date (
                    <a href="https://www.postgresql.org/docs/current/datatype-datetime.html">
                      timestamptz
                    </a>
                    )
                  </Tag>{" "}
                  the start time of the current subscription.
                </h4>
                <h4>
                  <Tag>
                    end_date (
                    <a href="https://www.postgresql.org/docs/current/datatype-datetime.html">
                      timestamptz
                    </a>
                    )
                  </Tag>
                  the end time of the current subscription.
                </h4>
                <p>
                  Please return a single row with a a column named{" "}
                  <Tag>usage_qty</Tag>. If you return more than one, we will use
                  the first one. If you return none, we will assume the usage is
                  0.{" "}
                </p>
                <p>
                  Full SQL support is available, including joins, subqueries,
                  CTEs, and window functions.
                </p>
                <Button
                  className="float-right"
                  onClick={() => {
                    formatSQL();
                  }}
                >
                  Format
                </Button>
                <AceEditor
                  width="80%"
                  mode="sql"
                  theme="github"
                  placeholder="SELECT * FROM events"
                  onChange={(newValue) => setCustomSQL(newValue)}
                  name="custom_sql"
                  highlightActiveLine
                  value={customSQL || ""}
                  showGutter
                  setOptions={{
                    enableBasicAutocompletion: true,
                    enableLiveAutocompletion: true,
                    enableSnippets: true,
                    showLineNumbers: true,
                    tabSize: 2,
                  }}
                />
              </div>
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
                                      "Please input a property name or delete this filter.",
                                  },
                                ]}
                                noStyle
                              >
                                <Select
                                  placeholder="property name"
                                  mode="tags"
                                  maxTagCount={1}
                                  style={{ width: "30%" }}
                                >
                                  {propertyNames.map((p) => (
                                    <Option value={p}>{p}</Option>
                                  ))}
                                </Select>
                              </Form.Item>
                              <Form.Item
                                name={[field.name, "operator"]}
                                rules={[
                                  {
                                    required: true,
                                    whitespace: true,
                                    message:
                                      "Please input an operator or delete this filter.",
                                  },
                                ]}
                              >
                                <Select
                                  onChange={(e) => {
                                    let tagsShown = false;
                                    if (e === "isin" || e === "isnotin") {
                                      tagsShown = true;
                                    } else {
                                      tagsShown = false;
                                    }
                                    setShowTags({
                                      ...showTags,
                                      [field.name]: tagsShown,
                                    });
                                  }}
                                  style={{ width: "50%" }}
                                >
                                  <Option value="isin">is one of</Option>
                                  <Option value="isnotin">is not one of</Option>
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
                                  dependencies={[field.name, "operator"]}
                                  validateTrigger={["onChange", "onBlur"]}
                                  rules={[
                                    ({ getFieldValue }) => ({
                                      validator(_, value) {
                                        if (showTags[field.name] || false) {
                                          if (
                                            Array.isArray(value) &&
                                            value.length >= 1
                                          ) {
                                            return Promise.resolve();
                                          }
                                          return Promise.reject(
                                            "Please select at least one value for this filter."
                                          );
                                        } else if (
                                          value === undefined ||
                                          value === null ||
                                          value === "" ||
                                          (Array.isArray(value) &&
                                            value.length === 0)
                                        ) {
                                          return Promise.reject(
                                            "Please input a comparison value or delete this filter."
                                          );
                                        }
                                        return Promise.resolve();
                                      },
                                    }),
                                  ]}
                                >
                                  {!showTags[field.name] || false ? (
                                    <InputNumber
                                      placeholder="comparison value"
                                      style={{ width: "100%" }}
                                    />
                                  ) : (
                                    <Select
                                      mode="tags"
                                      style={{ width: "100%" }}
                                      placeholder="Input 1...n values"
                                      options={[]}
                                    />
                                  )}
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
                  {errors?.length && errors.length > 0 ? (
                    <div>
                      {errors.map((el, idx) => (
                        <div className="text-red-700" key={idx}>
                          {el}
                        </div>
                      ))}
                    </div>
                  ) : null}
                </Panel>
                <Panel header="Advanced Settings" key="2">
                  {eventType === "gauge" && (
                    <Form.Item name="proration" label="Proration">
                      <Tooltip
                        placement="left"
                        title="You can define your proration in order to allow usage as a fractional amount of the granularity."
                      >
                        <Select
                          value={selectedProration}
                          onChange={handleProrationChange}
                        >
                          {/* <Select.Option
                        value="milliseconds"
                        disabled={disableOption("milliseconds")}
                      >
                        milliseconds
                      </Select.Option> */}
                          <Select.Option
                            value="seconds"
                            disabled={disableOption("seconds")}
                          >
                            second
                          </Select.Option>
                          <Select.Option
                            value="minutes"
                            disabled={disableOption("minutes")}
                          >
                            minute
                          </Select.Option>
                          <Select.Option
                            value="hours"
                            disabled={disableOption("hours")}
                          >
                            hour
                          </Select.Option>
                          <Select.Option
                            value="days"
                            disabled={disableOption("days")}
                          >
                            day
                          </Select.Option>
                          <Select.Option
                            value="months"
                            disabled={disableOption("months")}
                          >
                            month
                          </Select.Option>
                          <Select.Option
                            value="total"
                            disabled={disableOption("total")}
                          >
                            no proration
                          </Select.Option>
                        </Select>
                      </Tooltip>
                    </Form.Item>
                  )}
                  {eventType === "counter" && (
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
                  )}
                </Panel>
              </Collapse>
            )}
          </div>
        )}
      </Form>
    </Modal>
  );
}

export default CreateMetricForm;
