import React, { useContext, useEffect, useRef, useState } from "react";
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
  Table,
} from "antd";
import { DeleteOutlined } from "@ant-design/icons";
import "./UsageComponentForm.css";
import { Metrics } from "../../api/api";
import { MetricNameType, MetricType } from "../../types/metric-type";
import type { InputRef } from "antd";
import type { FormInstance } from "antd/es/form";
import { Tier } from "../../types/plan-type";

const { Option } = Select;
const EditableContext = React.createContext<FormInstance<any> | null>(null);
type EditableTableProps = Parameters<typeof Table>[0];

type ColumnTypes = Exclude<EditableTableProps["columns"], undefined>;

const validateTiers = (tiers: Tier[]) => {
  const response: {} = {};
  var currentStart = 0;
  var currentEnd: number | undefined;
  tiers.forEach((tier, index) => {
    if (index === 0) {
      currentStart = tier.range_start;
      currentEnd = tier.range_end;

      if (!["flat", "free", "per_unit"].includes(tier.type)) {
        return false;
      } else if (tier.type === "per_unit") {
        return (
          typeof tier.cost_per_batch === "number" &&
          typeof tier.metric_units_per_batch === "number" &&
          tier.metric_units_per_batch > 0 &&
          tier.cost_per_batch >= 0
        );
      } else if (tier.type === "flat") {
        return (
          typeof tier.cost_per_batch === "number" && tier.cost_per_batch >= 0
        );
      }

      //check if types are correct
    } else {
      if (currentEnd === undefined || tier.range_start < currentEnd) {
        return false;
      } else {
        currentStart = tier.range_start;
        currentEnd = tier.range_end;

        if (!["flat", "free", "per_unit"].includes(tier.type)) {
          return false;
        } else if (tier.type === "per_unit") {
          return (
            typeof tier.cost_per_batch === "number" &&
            typeof tier.metric_units_per_batch === "number" &&
            tier.metric_units_per_batch > 0 &&
            tier.cost_per_batch >= 0
          );
        } else if (tier.type === "flat") {
          return (
            typeof tier.cost_per_batch === "number" && tier.cost_per_batch >= 0
          );
        }
      }
    }
  });
  return response;
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
        dataIndex === "metric_units_per_batch"
      ) {
        return false;
      }
    } else if (record.type === "flat") {
      if (dataIndex === "metric_units_per_batch") {
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
        name={dataIndex}
        // rules={[
        //   {
        //     required: {record.range_end ? true : false},
        //     message: `${title} is required.`,
        //   },
        // ]}
      >
        {title === "Charge Type" ? (
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
        ) : (
          <Input
            ref={inputRef}
            type="number"
            onPressEnter={save}
            onBlur={save}
          />
        )}
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
  const [errorMessage, setErrorMessage] = useState("");

  const initialTier: Tier[] = [
    {
      type: "free",
      range_start: 0,
    },
  ];
  const [currentTiers, setCurrentTiers] = useState<Tier[]>(
    editComponentItem?.tiers ?? initialTier
  );
  const [rangeEnd, setRangeEnd] = useState<number>();

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

  const handleAdd = () => {
    //if range_end isn't null
    if (rangeEnd !== undefined) {
      const newTierDefault: Tier = {
        range_start: rangeEnd,
        type: "flat",
        cost_per_batch: 0,
      };
      setCurrentTiers([...currentTiers, newTierDefault]);
      console.log(currentTiers);
      setRangeEnd(rangeEnd);
      setErrorMessage("");
    } else {
      setErrorMessage("Please enter a range end");
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
    setRangeEnd(row.range_end);
    const item = newData[index];
    newData.splice(index, 1, {
      ...item,
      ...row,
    });
    setCurrentTiers(newData);
  };

  const handleDelete = (range_start: React.Key) => {
    console.log(range_start);
    const newData = currentTiers.filter(
      (item) => item.range_start !== range_start
    );
    setCurrentTiers(newData);
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
      editable: true,
    },
    {
      title: "Last Unit",
      dataIndex: "range_end",
      editable: true,
      render: (text: any, record: Tier) => {
        if (record.range_end === undefined || record.range_end === "") {
          return "∞";
        } else {
          return record.range_end;
        }
      },
    },
    {
      title: "Charge Type",
      dataIndex: "type",
      editable: true,
    },
    {
      title: "Amount ($)",
      dataIndex: "cost_per_batch",
      editable: true,
    },
    {
      title: "Units",
      dataIndex: "metric_units_per_batch",
      editable: true,
    },

    {
      title: "Delete",
      dataIndex: "delete",
      render: (_, record) =>
        currentTiers.length > 1 &&
        record.range_start != 0 && (
          <Button
            size="small"
            type="text"
            icon={<DeleteOutlined />}
            danger
            onClick={() => {
              console.log(record);
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
            console.log(values);

            if (validateTiers(currentTiers)) {
              handleComponentAdd({
                metric: values.metric,
                tiers: currentTiers,
              });

              form.submit();
              form.resetFields();
              setErrorMessage("");
            } else {
              setErrorMessage("Tiers are not valid");
            }
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
        <div className="grid grid-cols-12 space-x-4 mt-4 mb-8">
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

        <Table
          components={components}
          columns={columns}
          rowClassName={() => "editable-row"}
          dataSource={currentTiers}
          pagination={false}
        />
        <div className="flex justify-center w-full mt-4">
          <Button
            onClick={handleAdd}
            type="primary"
            style={{ marginBottom: 16 }}
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
