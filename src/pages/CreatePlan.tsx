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
  List,
} from "antd";
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import UsageComponentForm from "../components/UsageComponentForm";
import { useMutation } from "react-query";
import { MetricType } from "../types/metric-type";
import { toast, ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";

interface ComponentDisplay {
  metric: string;
  cost_per_metric: number;
  metric_amount_per_cost: number;
  free_amount: number;
}
interface UsageComponent {
  event_name: string;
  aggregation_type: string;
  cost: number;
  free_amount: number;
}

const CreatePlan = () => {
  const [visible, setVisible] = useState(false);
  const navigate = useNavigate();

  // const mutation = useMutation(
  //   (post: CustomerType) => Customer.createCustomer(post),
  //   {
  //     onSuccess: () => {
  //       setVisible(false);
  //       toast.success("Customer created successfully", {
  //         position: toast.POSITION.TOP_CENTER,
  //       });
  //     },
  //   }
  // );

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
      <Form.Provider
        onFormFinish={(name, { values, forms }) => {
          console.log(forms);
          if (name === "component_form") {
            const { create_plan } = forms;
            console.log(values);
            const components = create_plan.getFieldValue("components") || [];
            create_plan.setFieldsValue({ components: [...components, values] });
            setVisible(false);
          }
        }}
      >
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
          <Form.Item name="pay_in_advance">
            <Checkbox defaultChecked={true}>Pay In Advance </Checkbox>
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
          <Form.Item
            label="Usage Components"
            shouldUpdate={(prevValues, curValues) =>
              prevValues.components !== curValues.components
            }
          >
            {({ getFieldValue }) => {
              const components: ComponentDisplay[] =
                getFieldValue("components") || [];
              return components.length ? (
                <List grid={{ gutter: 16, column: 4 }}>
                  {components.map((component, index) => (
                    <List.Item key={index} className="user">
                      <Card title={component.metric}>
                        <p>
                          <b>Cost:</b> {component.cost_per_metric} per{" "}
                          {component.metric_amount_per_cost} events{" "}
                        </p>
                        <br />
                        <p>
                          <b>Free Amount Per Billing Cycle:</b>{" "}
                          {component.free_amount}
                        </p>
                      </Card>
                    </List.Item>
                  ))}
                </List>
              ) : null;
            }}
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
      </Form.Provider>
      <ToastContainer />
    </div>
  );
};

export default CreatePlan;
