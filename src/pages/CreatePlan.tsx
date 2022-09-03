import {
  Button,
  Checkbox,
  Form,
  Card,
  Input,
  Select,
  InputNumber,
  PageHeader,
  Popconfirm,
} from "antd";
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import UsageComponentForm from "../components/UsageComponentForm";

interface UsageComponent {
  event_name: string;
  aggregation_type: string;
  cost: number;
  free_amount: number;
}

const CreatePlan = () => {
  const [visible, setVisible] = useState(false);
  const [components, setComponents] = useState<UsageComponent[]>([]);
  const navigate = useNavigate();
  const onFinish = (values: any) => {
    console.log("Success:", values);
  };

  const onFinishFailed = (errorInfo: any) => {
    console.log("Failed:", errorInfo);
  };

  const hideUserModal = () => {
    setVisible(false);
  };

  const showUserModal = () => {
    setVisible(true);
  };

  const goBackPage = () => {
    navigate(-1);
  };

  const submitPricingPlan = () => {
    console.log("Submit Pricing Plan");
    navigate("/plans");
  };

  return (
    <div className="flex flex-col">
      <PageHeader
        className="site-page-header"
        onBack={goBackPage}
        title="Create Plan"
      />
      <Form
        name="create_plan"
        initialValues={{ remember: true }}
        onFinish={onFinish}
        onFinishFailed={onFinishFailed}
        autoComplete="off"
      >
        <Form.Item label="Plan Name">
          <Input placeholder="Ex: Starter Plan" />
        </Form.Item>
        <Form.Item label="Description">
          <Input
            type="textarea"
            placeholder="Ex: Cheapest plan for small scale businesses"
          />
        </Form.Item>
        <Form.Item label="Billing Interval">
          <Select>
            <Select.Option value="weekly">Weekly</Select.Option>
            <Select.Option value="monthly">Monthly</Select.Option>
            <Select.Option value="yearly">Yearly</Select.Option>
          </Select>
        </Form.Item>

        <Form.Item label="Recurring Cost">
          <InputNumber addonBefore="$" defaultValue={0} precision={2} />
        </Form.Item>
        <Form.Item>
          <Checkbox defaultChecked={true}>Pay In Advance </Checkbox>
        </Form.Item>
        {components.map((component, index) => (
          <Card>
            <p>{component.event_name}</p>
          </Card>
        ))}
        <Form.Item>
          <Button
            htmlType="button"
            style={{ margin: "0 8px" }}
            onClick={showUserModal}
          >
            Add Usage Component
          </Button>
        </Form.Item>

        <Form.Item>
          <Popconfirm
            title="Submit"
            onConfirm={submitPricingPlan}
            onVisibleChange={() => console.log("visible change")}
          >
            <Button type="primary" className="bg-info" htmlType="submit">
              Submit
            </Button>
          </Popconfirm>
        </Form.Item>
      </Form>

      <UsageComponentForm visible={visible} onCancel={hideUserModal} />
    </div>
  );
};

export default CreatePlan;
