import { Modal, Form, Input, Select } from "antd";
import { MetricType } from "../types/metric-type";
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

  form.setFieldsValue({
    event_name: props.state.event_name,
    aggregation_type: props.state.aggregation_type,
    property_name: props.state.property_name,
  });

  return (
    <Modal
      visible={props.visible}
      title={props.state.title}
      okText="Create"
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
          name="aggregation_type"
          label="Aggregation Type"
          rules={[
            {
              required: true,
              message: "Unique customer_id is required",
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
            prevValues.aggregation_type !== currentValues.aggregation_type
          }
        >
          {({ getFieldValue }) =>
            getFieldValue("aggregation_type") === "sum" ||
            getFieldValue("aggregation_type") === "max" ||
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
      </Form>
    </Modal>
  );
};

export default CreateMetricForm;
