/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable react/no-unused-prop-types */
/* eslint-disable no-unused-expressions */
/* eslint-disable no-plusplus */
/* eslint-disable camelcase */
/* eslint-disable no-console */
/* eslint-disable no-shadow */
/* eslint-disable react/destructuring-assignment */
import React, { Ref, useContext, useEffect, useRef, useState } from "react";
import { Button, Form, InputNumber, Modal, Select, Table } from "antd";
import { DeleteOutlined } from "@ant-design/icons";
import "./UsageComponentForm.css";
import type { InputRef } from "antd";
import type { FormInstance } from "antd/es/form";
import { Metrics } from "../../api/api";
import { MetricType } from "../../types/metric-type";
import { Tier } from "../../types/plan-type";
import { CurrencyType } from "../../types/pricing-unit-type";

const { Option } = Select;

const EditableContext = React.createContext<FormInstance | null>(null);
type EditableTableProps = Parameters<typeof Table>[0];

type ColumnTypes = Exclude<EditableTableProps["columns"], undefined>;
type ValidateTiersType = { isValid: boolean; message: string }[];
const validateTiers = (tiers: Tier[]): ValidateTiersType => {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
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

interface EditableRowProps {
  index: number;
}

const EditableRow: React.FC<EditableRowProps> = () => {
  const [form] = Form.useForm();

  return (
    <Form form={form} component={false}>
      <EditableContext.Provider value={form}>
        <tr />
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
  const form = useContext(EditableContext);

  useEffect(() => {
    if (editing) {
      inputRef.current?.focus();
    }
  }, [editing]);

  const toggleEdit = () => {
    setEditing(!editing);
    form?.setFieldsValue({ [dataIndex]: record[dataIndex] });
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
      const values = await form?.validateFields();
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
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                <Select onChange={save} ref={inputRef as any} onBlur={save}>
                  <Option value="per_unit">Per Unit</Option>
                  <Option value="free">Free</Option>
                  <Option value="flat">Flat</Option>
                </Select>
              );
            case "Rounding Type":
              return (
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                <Select onChange={save} ref={inputRef as any} onBlur={save}>
                  <Option value="round_up">round_up</Option>
                  <Option value="round_down">round_down</Option>
                  <Option value="round_nearest">round_nearest</Option>
                  <Option value="no_rounding">no_rounding</Option>
                </Select>
              );
            default:
              return (
                <InputNumber
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  ref={inputRef as any}
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
        aria-hidden
        className="editable-cell-value-wrap"
        style={{ paddingRight: 24 }}
        onClick={
          validateEditable(dataIndex, record)
            ? toggleEdit
            : () => {
                //
              }
        }
      >
        {children}
      </div>
    );
  }

  // eslint-disable-next-line react/jsx-props-no-spreading
  return <td {...restProps}>{childNode}</td>;
};

type Props = {
  visible?: boolean;
  onCancel: () => void;
  componentsData: any;
  handleComponentAdd: (s: any) => void;
  editComponentItem: any;
  setEditComponentsItem: (s: any) => void;
  currency: CurrencyType;
};
function UsageComponentForm({
  handleComponentAdd,
  visible,
  onCancel,
  editComponentItem,
  setEditComponentsItem,
  currency,
}: Props) {
  const [form] = Form.useForm();
  const [metrics, setMetrics] = useState<string[]>([]);
  const [metricObjects, setMetricObjects] = useState<MetricType[]>([]);
  const [metricGauge, setMetricGauge] = useState<boolean>(false);
  const selectedMetricName = Form.useWatch("metric", form);

  const [prorationGranularity] = useState<string>(
    editComponentItem?.proration_granularity ?? "total"
  );

  const initalData = editComponentItem ?? null;
  const [errorMessage, setErrorMessage] = useState("");
  const buttonRef = useRef<HTMLButtonElement | undefined>(undefined);
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
    // eslint-disable-next-line no-unsafe-optional-chaining
    editComponentItem?.tiers[editComponentItem?.tiers.length - 1]?.range_end ??
      undefined
  );

  console.log(metricGauge);

  useEffect(() => {
    setMetricGauge(
      metricObjects.find((metric) => metric.metric_name === selectedMetricName)
        ?.metric_type === "gauge"
    );
  }, [metricObjects, selectedMetricName]);

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

  const handleSave = (row: Tier) => {
    const newData = [...currentTiers];
    const r = { ...row };
    const index = newData.findIndex(
      (item) => row.range_start === item.range_start
    );
    if (row.type === "free") {
      r.cost_per_batch = 0;
      r.metric_units_per_batch = undefined;
    }
    setRangeEnd(row.range_end);
    const item = newData[index];
    newData.splice(index, 1, {
      ...item,
      ...r,
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
      render: (_text, record: object) => {
        const r: Tier = record as Tier;
        if (r.range_end === undefined || r.range_end === null) {
          return "∞";
        }
        return r.range_end;
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
      title: `Amount (${currency.symbol})`,
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
      render: (_, record: object) => {
        const r: Tier = record as Tier;
        if (r.type === "flat" || r.type === "free") {
          return "-";
        }
        return r.metric_units_per_batch;
      },
    },
    {
      title: "Rounding Type",
      dataIndex: "batch_rounding_type",
      width: "23%",
      align: "center",
      editable: true,
      render: (_, record: object) => {
        const r: Tier = record as Tier;
        if (r.type === "flat" || r.type === "free") {
          return "-";
        }
        return <div>{r.batch_rounding_type}</div>;
      },
    },

    {
      title: "Delete",
      dataIndex: "delete",
      width: "8%",
      align: "center",
      render: (_, record) => {
        const r: Tier = record as Tier;
        return (
          currentTiers.length > 1 &&
          r.range_start !== 0 && (
            <Button
              size="small"
              type="text"
              icon={<DeleteOutlined />}
              danger
              onClick={() => {
                handleDelete(r.range_start);
              }}
            />
          )
        );
      },
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
      okText="Create New Component"
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
      }}
      onOk={() => {
        form.validateFields().then((values) => {
          if (
            validateTiers(currentTiers).every((item) => item.isValid === true)
          ) {
            const currentMetric = metricObjects.find(
              (metric) => metric.metric_name === form.getFieldValue("metric")
            );
            handleComponentAdd({
              metric: values.metric,
              tiers: currentTiers,
              proration_granularity: prorationGranularity,
              metric_id: currentMetric?.metric_id,
            });

            form.submit();
            form.resetFields();
            setErrorMessage("");
          }
        });
      }}
    >
      <Form
        form={form}
        layout="horizontal"
        name="component_form"
        initialValues={initalData}
      >
        <div className="grid grid-cols-12 space-x-4 mt-4 mb-8">
          <Form.Item
            label="Metric"
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
                <Option key={metric_name} value={metric_name}>
                  {metric_name}
                </Option>
              ))}
            </Select>
          </Form.Item>
        </div>

        <Table
          components={components}
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          columns={columns as any}
          rowClassName={() => "editable-row"}
          dataSource={currentTiers}
          pagination={false}
        />
        <div className="flex justify-center w-full mt-4">
          <Button
            onClick={handleAdd}
            ref={buttonRef as Ref<HTMLElement> | undefined}
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
      </Form>
    </Modal>
  );
}

export default UsageComponentForm;
