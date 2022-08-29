import { Button, Checkbox, Form, Input, Select, InputNumber } from "antd";
import React, { useState } from "react";
import UsageComponentForm from "../components/UsageComponentForm";

const CreatePlan = () => {
  const [visible, setVisible] = useState(false);
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

  return (
    <div className="flex flex-col">
      <h1>Create Plan</h1>
      <Form
        name="create_plan"
        labelCol={{ span: 8 }}
        wrapperCol={{ span: 16 }}
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
          <InputNumber addonBefore="$" defaultValue={20} precision={2} />
        </Form.Item>
        <Form.Item>
          <Checkbox>Pay In Advance </Checkbox>
        </Form.Item>
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
          <Button type="primary" className="bg-info" htmlType="submit">
            Submit
          </Button>
        </Form.Item>
      </Form>

      <UsageComponentForm visible={visible} onCancel={hideUserModal} />
    </div>
  );
};

export default CreatePlan;
