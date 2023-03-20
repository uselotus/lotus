import React, { useContext, useEffect, useRef, useState } from "react";
import {
  Button,
  Collapse,
  Form,
  InputNumber,
  Modal,
  Select,
  Table,
  Input,
  Checkbox,
} from "antd";
import { DeleteOutlined } from "@ant-design/icons";
import "./UsageComponentForm.css";
import type { InputRef } from "antd";
import type { FormInstance } from "antd/es/form";
import { Metrics } from "../../api/api";
import { MetricType } from "../../types/metric-type";
import { Tier } from "../../types/plan-type";
import { CurrencyType } from "../../types/pricing-unit-type";

const { Option } = Select;
const { Panel } = Collapse;

function resetValidationLogic(reset_unit, invoicing_unit) {
  if (invoicing_unit && reset_unit) {
    if (reset_unit === "week" && invoicing_unit === "day") {
      return Promise.reject(
        "Reset interval unit must be less than or equal to invoicing interval unit"
      );
    }
    if (reset_unit === "month" && ["day", "week"].includes(invoicing_unit)) {
      return Promise.reject(
        "Reset interval unit must be less than or equal to invoicing interval unit"
      );
    }
    if (
      reset_unit === "year" &&
      ["day", "week", "month"].includes(invoicing_unit)
    ) {
      return Promise.reject(
        "Reset interval unit must be less than or equal to invoicing interval unit"
      );
    }
  }
  return Promise.resolve();
}

const EditableContext = React.createContext<FormInstance<any> | null>(null);
type EditableTableProps = Parameters<typeof Table>[0];

type ColumnTypes = Exclude<EditableTableProps["columns"], undefined>;
type ValidateTiersType = { isValid: boolean; message: string }[];
const validateTiers = (tiers: Tier[]): ValidateTiersType => {
  let currentStart = 0;
  let currentEnd: number | undefined;

  const arr2: ValidateTiersType = tiers.map((tier, index) => {
    if (index === 0) {
      if (
        tier.range_end !== undefined &&
        tier.range_end !== null &&
        tier.range_start >= tier.range_end
      ) {
        return { isValid: false, message: "Range is not valid" };
      }
      currentStart = tier.range_start;
      currentEnd = tier.range_end;

      if (!["flat", "free", "per_unit"].includes(tier.type)) {
        return { isValid: false, message: "Tiers are not valid" };
      }
      if (tier.type === "per_unit") {
        return typeof tier.batch_rounding_type === "string" &&
          typeof tier.cost_per_batch === "number" &&
          typeof tier.metric_units_per_batch === "number" &&
          tier.metric_units_per_batch > 0 &&
          tier.cost_per_batch >= 0 === true
          ? { isValid: true, message: "" }
          : { isValid: false, message: "Unit is not valid." };
      }
      if (tier.type === "flat") {
        return {
          isValid:
            typeof tier.cost_per_batch === "number" && tier.cost_per_batch >= 0,
          message: "",
        };
      }

      // check if types are correct
    } else {
      if (
        currentEnd === undefined ||
        tier.range_start < currentEnd ||
        tier.range_start > currentEnd + 1 ||
        (tier.range_end !== undefined &&
          tier.range_end !== null &&
          tier.range_start >= tier.range_end)
      ) {
        return { isValid: false, message: "Range is not valid." };
      }
      currentStart = tier.range_start;
      currentEnd = tier.range_end;

      if (!["flat", "free", "per_unit"].includes(tier.type)) {
        return { isValid: false, message: "Tiers are not valid" };
      }
      if (tier.type === "per_unit") {
        return typeof tier.cost_per_batch === "number" &&
          typeof tier.metric_units_per_batch === "number" &&
          tier.metric_units_per_batch > 0 &&
          tier.cost_per_batch >= 0 === true
          ? { isValid: true, message: "" }
          : { isValid: false, message: "Unit is not valid." };
      }
      if (tier.type === "flat") {
        return {
          isValid:
            typeof tier.cost_per_batch === "number" && tier.cost_per_batch >= 0,
          message: "",
        };
      }
    }
    return { isValid: true, message: "" };
  });

  return arr2;
};

interface Item {
  key: string;
  name: string;
  age: string;
  address: string;
}

const EditableRow: React.FC<EditableRowProps> = ({ index, ...props }) => {
  const [form] = Form.useForm();

  return (
    <Form form={form} component={false}>
      <EditableContext.Provider value={form}>
        <tr {...props} />
      </EditableContext.Provider>
    </Form>
  );
};

interface EditableCellProps {
  title: React.ReactNode;
  editable: boolean;
  children: React.ReactNode;
  dataIndex: keyof Tier;
  record: Tier;
  handleSave: (record: Tier) => void;
}

interface EditableRowProps {
  index: number;
}

const EditableCell: React.FC<EditableCellProps> = ({
  title,
  editable,
  children,
  dataIndex,
  record,
  handleSave,
  ...restProps
}) => {
  const [editing, setEditing] = useState(false);
  const inputRef = useRef<InputRef>(null);
  const form = useContext(EditableContext)!;

  useEffect(() => {
    if (editing) {
      inputRef.current!.focus();
    }
  }, [editing]);

  const toggleEdit = () => {
    setEditing(!editing);
    form.setFieldsValue({ [dataIndex]: record[dataIndex] });
  };

  const validateEditable = (dataIndex: keyof Tier, record: Tier) => {
    if (record.type === "free") {
      if (
        dataIndex === "cost_per_batch" ||
        dataIndex === "metric_units_per_batch" ||
        dataIndex === "batch_rounding_type"
      ) {
        return false;
      }
    } else if (record.type === "flat") {
      if (
        dataIndex === "metric_units_per_batch" ||
        dataIndex === "batch_rounding_type"
      ) {
        return false;
      }
    }
    return true;
  };
  const save = async () => {
    try {
      const values = await form.validateFields();
      toggleEdit();
      handleSave({ ...record, ...values });
    } catch (errInfo) {
      console.log("Save failed:", errInfo);
    }
  };

  let childNode = children;

  if (editable) {
    childNode = editing ? (
      <Form.Item
        style={{ margin: 0 }}
        className="w-full"
        name={dataIndex}
        // rules={[
        //   {
        //     required: {record.range_end ? true : false},
        //     message: `${title} is required.`,
        //   },
        // ]}
      >
        {(() => {
          switch (title) {
            case "Charge Type":
              return (
                <Select
                  onChange={save}
                  ref={inputRef}
                  onBlur={save}
                  onPressEnter={save}
                >
                  <Option value="per_unit">Per Unit</Option>
                  <Option value="free">Free</Option>
                  <Option value="flat">Flat</Option>
                </Select>
              );
            case "Rounding Type":
              return (
                <Select
                  onChange={save}
                  ref={inputRef}
                  onBlur={save}
                  onPressEnter={save}
                >
                  <Option value="round_up">round_up</Option>
                  <Option value="round_down">round_down</Option>
                  <Option value="round_nearest">round_nearest</Option>
                  <Option value="no_rounding">no_rounding</Option>
                </Select>
              );
            default:
              return (
                <InputNumber
                  ref={inputRef}
                  onPressEnter={save}
                  onBlur={save}
                  min={0}
                />
              );
          }
        })()}
      </Form.Item>
    ) : (
      <div
        className="editable-cell-value-wrap"
        style={{ paddingRight: 24 }}
        onClick={validateEditable(dataIndex, record) ? toggleEdit : () => {}}
      >
        {children}
      </div>
    );
  }

  return <td {...restProps}>{childNode}</td>;
};

type Props = {
  visible?: any;
  onCancel: () => void;
  componentsData: any;
  handleComponentAdd: (s: any) => void;
  editComponentItem: any;
  setEditComponentsItem: (s: any) => void;
  currency: CurrencyType;
  planDuration: string;
};
function UsageComponentForm({
  handleComponentAdd,
  visible,
  onCancel,
  editComponentItem,
  setEditComponentsItem,
  currency,
  planDuration,
}: Props) {
  const [form] = Form.useForm();
  const [metrics, setMetrics] = useState<string[]>([]);
  const [gaugeGranularity, setGaugeGranularity] = useState<string | null>(null);
  const [metricObjects, setMetricObjects] = useState<MetricType[]>([]);
  const [metricGauge, setMetricGauge] = useState<boolean>(false);
  const selectedMetricName = Form.useWatch("metric", form);
  const [componentIntervalOptions, setComponentIntervalOptions] = useState<
    string[]
  >([]);
  const [componentIntervalUnitLimit, setComponentIntervalUnitLimit] =
    useState<number>(100);

  const [prepaid, setPrepaid] = useState<boolean>(
    editComponentItem?.prepaid_charge ?? false
  );
  console.log(prepaid);
  const backupDefaultFormValues = {
    charge_behavior:
      editComponentItem?.prepaid_charge?.charge_behavior ?? "full",
    units: editComponentItem?.prepaid_charge?.units ?? null,
  };

  const initialData = Object.assign(
    {},
    backupDefaultFormValues,
    editComponentItem
  );
  console.log(editComponentItem);
  const [errorMessage, setErrorMessage] = useState("");
  const buttonRef = useRef<HTMLButtonElement | undefined>(undefined!);
  const initialTier: Tier[] = [
    {
      type: "free",
      range_start: 0,
    },
  ];
  const [currentTiers, setCurrentTiers] = useState<Tier[]>(
    editComponentItem?.tiers ?? initialTier
  );
  const [rangeEnd, setRangeEnd] = useState<number | undefined>(
    editComponentItem?.tiers[editComponentItem?.tiers.length - 1]?.range_end ??
      undefined
  );

  useEffect(() => {
    if (planDuration === "monthly") {
      setComponentIntervalOptions(["day", "week"]);
    } else if (planDuration === "yearly") {
      setComponentIntervalOptions(["day", "month"]);
    } else if (planDuration === "quarterly") {
      setComponentIntervalOptions(["day", "week", "month"]);
    }
  }, [planDuration]);

  useEffect(() => {
    setMetricGauge(
      metricObjects.find((metric) => metric.metric_name === selectedMetricName)
        ?.metric_type === "gauge"
    );
  }, [selectedMetricName]);

  useEffect(() => {
    Metrics.getMetrics().then((res) => {
      const data = res;
      if (data) {
        const metricList: string[] = [];
        for (let i = 0; i < data.length; i++) {
          if (typeof data[i].metric_name !== undefined) {
            metricList.push(data[i].metric_name as unknown as string);
          }

          if (editComponentItem?.metric === data[i].metric_name) {
            setMetricGauge(data[i].metric_type === "gauge");
          }
        }
        setMetrics(metricList);
        setMetricObjects(data);
      }
    });
  }, []);

  const handleAdd = () => {
    // if range_end isn't null
    if (rangeEnd !== undefined && rangeEnd !== null) {
      const newTierDefault: Tier = {
        range_start: rangeEnd,
        type: "flat",
        cost_per_batch: 0,
      };
      setCurrentTiers([...currentTiers, newTierDefault]);
      setRangeEnd(undefined);
      setErrorMessage("");
    } else {
      setErrorMessage("Please enter a non-infinite range end");
    }
  };

  const handleSelectMetric = (metric_name: string) => {
    const currentMetric = metricObjects.find(
      (metric) => metric.metric_name === metric_name
    );
    if (currentMetric && currentMetric.metric_type === "gauge") {
      if (currentMetric.granularity) {
        setGaugeGranularity(currentMetric.granularity);
      } else {
        setGaugeGranularity("total");
      }
    } else {
      setGaugeGranularity(null);
    }
  };

  const handleSave = (row: Tier) => {
    const newData = [...currentTiers];
    const index = newData.findIndex(
      (item) => row.range_start === item.range_start
    );
    if (row.type === "free") {
      row.cost_per_batch = 0;
      row.metric_units_per_batch = undefined;
    }

    if (row.type === "per_unit" && !row.batch_rounding_type) {
      row.batch_rounding_type = "no_rounding";
    }
    if (row.type === "per_unit" && !row.metric_units_per_batch) {
      row.metric_units_per_batch = 1;
    }

    setRangeEnd(row.range_end);
    const item = newData[index];
    newData.splice(index, 1, {
      ...item,
      ...row,
    });
    setCurrentTiers(newData);
  };

  const handleDelete = (range_start: React.Key) => {
    const newData = currentTiers.filter(
      (item) => item.range_start !== range_start
    );
    setCurrentTiers(newData);
    setRangeEnd(newData[newData.length - 1].range_end);
  };

  const components = {
    body: {
      row: EditableRow,
      cell: EditableCell,
    },
  };

  const defaultColumns: (ColumnTypes[number] & {
    editable?: boolean;
    dataIndex: string;
  })[] = [
    {
      title: "First Unit",
      dataIndex: "range_start",
      width: "17%",
      align: "center",
      editable: true,
    },
    {
      title: "Last Unit",
      dataIndex: "range_end",
      width: "17%",
      align: "center",

      editable: true,
      render: (text: any, record: Tier) => {
        if (record.range_end === undefined || record.range_end === null) {
          return "∞";
        }
        return record.range_end;
      },
    },
    {
      title: "Charge Type",
      dataIndex: "type",
      editable: true,
      width: "17%",
      align: "center",
    },
    {
      title: `Amount (${currency?.symbol})`,
      dataIndex: "cost_per_batch",
      editable: true,
      align: "center",
      width: "13%",
    },
    {
      title: "Units",
      dataIndex: "metric_units_per_batch",
      width: "13%",
      align: "center",
      editable: true,
      render: (text: any, record: Tier) => {
        if (record.type === "flat" || record.type === "free") {
          return "-";
        }
        return record.metric_units_per_batch;
      },
    },
    {
      title: "Rounding Type",
      dataIndex: "batch_rounding_type",
      width: "23%",
      align: "center",
      editable: true,
      render: (text: any, record: Tier) => {
        if (record.type === "flat" || record.type === "free") {
          return "-";
        }
        return <div>{record.batch_rounding_type}</div>;
      },
    },

    {
      title: "Delete",
      dataIndex: "delete",
      width: "8%",
      align: "center",
      render: (_, record) =>
        currentTiers.length > 1 &&
        record.range_start != 0 && (
          <Button
            size="small"
            type="text"
            icon={<DeleteOutlined />}
            danger
            onClick={() => {
              handleDelete(record.range_start);
            }}
          />
        ),
    },
  ];

  const columns = defaultColumns.map((col) => {
    if (!col.editable) {
      return col;
    }
    return {
      ...col,
      onCell: (record: Tier) => ({
        record,
        editable: col.editable,
        dataIndex: col.dataIndex,
        title: col.title,
        handleSave,
      }),
    };
  });

  useEffect(() => {
    // logic for disabling add tier button when there's an error
    if (validateTiers(currentTiers).some((item) => item.isValid === false)) {
      buttonRef.current ? (buttonRef.current.disabled = true) : null;
      const errorMessage = validateTiers(currentTiers).filter(
        (item) => item.isValid === false
      )[0].message;
      setErrorMessage(errorMessage);
    } else {
      buttonRef.current ? (buttonRef.current.disabled = false) : null;
      setErrorMessage("");
    }
  }, [currentTiers]);
  return (
    <Modal
      visible={visible}
      title="Create Component"
      okText={editComponentItem ? "Update Component" : "Create New Component"}
      okType="primary"
      cancelText="Cancel"
      width={900}
      okButtonProps={{
        className: "bg-black text-white justify-self-end",
        disabled: errorMessage.length > 0,
      }}
      onCancel={() => {
        onCancel();
        form.resetFields();
        setEditComponentsItem(undefined);
        setPrepaid(false);
        setErrorMessage("");
      }}
      onOk={() => {
        form
          .validateFields()
          .then((values) => {
            if (
              validateTiers(currentTiers).every((item) => item.isValid === true)
            ) {
              const currentMetric = metricObjects.find(
                (metric) => metric.metric_name === form.getFieldValue("metric")
              );

              handleComponentAdd({
                metric: values.metric,
                tiers: currentTiers,
                metric_id: currentMetric?.metric_id,
                reset_interval_count: values.reset_interval_count,
                reset_interval_unit: values.reset_interval_unit,
                invoicing_interval_count: values.invoicing_interval_count,
                invoicing_interval_unit: values.invoicing_interval_unit,
                bulk_pricing_enabled: values.bulk_pricing_enabled,
                id: initialData?.id,
                prepaid_charge: prepaid
                  ? {
                      units: values.units || null,
                      charge_behavior: values.charge_behavior,
                    }
                  : null,
              });

              form.submit();
              form.resetFields();
              setPrepaid(false);
              setErrorMessage("");
            }
          })
          .catch((info) => {});
      }}
    >
      <Form
        form={form}
        layout="horizontal"
        name="component_form"
        initialValues={initialData}
      >
        <div className="grid grid-cols-12 space-x-4 mt-4 mb-8">
          <Form.Item
            label="Metric"
            className="col-span-11"
            name="metric"
            labelCol={{ span: 24 }}
            wrapperCol={{ span: 24 }}
            rules={[
              {
                required: true,
                message: "Please select a metric",
              },
            ]}
          >
            <Select onSelect={(value) => handleSelectMetric(value)}>
              {metrics?.map((metric_name) => (
                <Option value={metric_name}>{metric_name}</Option>
              ))}
            </Select>
          </Form.Item>
        </div>
        {gaugeGranularity && gaugeGranularity !== "total" && (
          <p className="text-darkgold mb-4">
            When inputting the price for this metric, you will be inputting the
            price per {gaugeGranularity.slice(0, -1)}
          </p>
        )}
        {gaugeGranularity === "total" && (
          <p className="text-darkgold mb-4">
            When inputting the price for this metric, you will be inputting the
            price per {planDuration.slice(0, -2)}
          </p>
        )}
        <Table
          components={components}
          columns={columns}
          rowClassName={() => "editable-row"}
          dataSource={currentTiers}
          pagination={false}
        />
        <div className="flex w-full mt-4">
          <Form.Item name="bulk_pricing_enabled" valuePropName="checked">
            <Checkbox>Bulk pricing</Checkbox>
          </Form.Item>
        </div>
        <div className="flex justify-center w-full mt-4">
          <Button
            onClick={handleAdd}
            ref={buttonRef}
            type="primary"
            style={{ marginBottom: 16 }}
            disabled={errorMessage.length > 0}
          >
            Add Tier
          </Button>
        </div>
        {errorMessage !== "" && (
          <p className="flex justify-center text-danger">{errorMessage}</p>
        )}
        <div className="mt-8 mb-12 space-y-6">
          <Collapse
            className="col-span-full bg-white py-8 rounded"
            defaultActiveKey={prepaid ? [1] : []}
          >
            <Panel header="Pre-Paid Usage" key="1">
              <div className="grid grid-cols-2 gap-8">
                <Form.Item>
                  <Checkbox
                    checked={prepaid}
                    onChange={(e) => {
                      setPrepaid(!prepaid);
                      if (e.target.checked) {
                        form.setFieldValue("units", null);
                      } else {
                        form.setFieldValue("units", null);
                      }
                    }}
                  >
                    Charge a fixed number of units in advance.
                  </Checkbox>
                </Form.Item>
              </div>

              {prepaid && (
                <div>
                  <div className="mb-8">
                    (Optional) Add a number of initial pre-paid units to the
                    plan.
                  </div>

                  <Form.Item name="units">
                    <Input type="number" placeholder="Pre-paid units" />
                  </Form.Item>
                </div>
              )}

              {prepaid && (
                <div>
                  <div className="mb-8">
                    How should changes to the number of pre-paid units be
                    charged?
                  </div>
                  <Form.Item name="charge_behavior">
                    <Select>
                      <Option value="full">Full</Option>
                      <Option value="prorate">Prorate</Option>
                    </Select>
                  </Form.Item>
                </div>
              )}

              {/* <div className="grid grid-flow-col items-center mb-8">
                <p>Property:</p>
                <Input
                  onChange={(e) => {
                    setSeparateByProperties([e.target.value]);
                  }}
                  value={separateByProperties[0]}
                ></Input>
              </div>
              {separateByProperties &&
                separateByProperties[0] !== "" &&
                separateByProperties[0] !== undefined && (
                  <p className=" text-darkgold mb-8">
                    Important: Only events that contain the property with name{" "}
                    {separateByProperties} will be counted under this metric.
                  </p>
                )} */}

              {/* {metricGauge === true && (
                <Fragment>
                  <div className="separator mb-8"></div>
                  <div className="grid grid-flow-col items-center mb-4">
                    <p>Proration Granularity:</p>
                    <Select
                      onChange={(value) => {
                        setProrationGranularity(value);
                      }}
                      value={prorationGranularity}
                    >
                      {generateValidProrationGranularity().map(
                        (granularity) => (
                          <Option value={granularity}>{granularity}</Option>
                        )
                      )}
                      <Option value="total">none</Option>
                    </Select>
                  </div>
                  {prorationGranularity === "total" && (
                    <p className=" text-darkgold mb-4">
                      Proration will not be applied to this component.
                    </p>
                  )}
                </Fragment>
              )} */}
            </Panel>
          </Collapse>
          <Collapse
            className="col-span-full bg-white py-8 rounded"
            defaultActiveKey={initialData ? [1] : []}
          >
            <Panel header="Component Settings" key="1">
              <div className="mb-8">
                <p className="mb-4">
                  <b>
                    How often does the usage for this component get invoiced?
                  </b>
                </p>

                <div className="grid grid-cols-2 mb-4 gap-8">
                  <Form.Item
                    name="invoicing_interval_count"
                    label="Invoicing Interval"
                  >
                    <Input type="number" placeholder="N/A" />
                  </Form.Item>
                  <Form.Item name="invoicing_interval_unit">
                    <Select>
                      {componentIntervalOptions.map((option) => (
                        <Option value={option}>{option}s</Option>
                      ))}
                      <Option value={null}>Same as plan duration</Option>
                    </Select>
                  </Form.Item>
                </div>
                <p className="mb-4">
                  <b>How often does the usage reset for this component?</b>
                </p>
                <div className="grid grid-cols-2 mb-4 gap-8">
                  <Form.Item name="reset_interval_count" label="Reset Interval">
                    <Input type="number" placeholder="N/A" />
                  </Form.Item>
                  <Form.Item
                    name="reset_interval_unit"
                    rules={[
                      ({ getFieldValue }) => ({
                        validator(_, value) {
                          const invoicingIntervalUnit = getFieldValue(
                            "invoicing_interval_unit"
                          );
                          return resetValidationLogic(
                            value,
                            invoicingIntervalUnit
                          );
                        },
                      }),
                    ]}
                  >
                    <Select>
                      {componentIntervalOptions.map((option) => (
                        <Option value={option}>{option}s</Option>
                      ))}
                      <Option value={null}>Same as plan duration</Option>
                    </Select>
                  </Form.Item>
                </div>
              </div>
            </Panel>
          </Collapse>
        </div>
      </Form>
    </Modal>
  );
}

export default UsageComponentForm;
