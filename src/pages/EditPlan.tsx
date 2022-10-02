import {
  Button,
  Checkbox,
  Form,
  Card,
  Input,
  Select,
  InputNumber,
  PageHeader,
  List,
  Divider,
  Radio,
} from "antd";
import { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import UsageComponentForm from "../components/UsageComponentForm";
import { useMutation } from "react-query";
import { MetricNameType } from "../types/metric-type";
import { toast } from "react-toastify";
import { Metrics } from "../api/api";
import { CreatePlanType, CreateComponent, PlanType } from "../types/plan-type";
import { Plan } from "../api/api";

interface ComponentDisplay {
  metric: string;
  cost_per_batch: number;
  metric_units_per_batch: number;
  free_metric_units: number;
  max_metric_units: number;
}
interface CustomizedState {
  plan: PlanType;
}

const EditPlan = () => {
  const [visible, setVisible] = useState(false);
  const navigate = useNavigate();
  const [metrics, setMetrics] = useState<string[]>([]);
  const [form] = Form.useForm();
  const location = useLocation();
  const [featureVisible, setFeatureVisible] = useState(false);
  const [selectedComponent, setSelectedComponent] =
    useState<ComponentDisplay>();

  const { plan } = location.state as CustomizedState;

  const [planFeatures, setPlanFeatures] = useState<string[]>([]);

  useEffect(() => {
    Metrics.getMetrics().then((res) => {
      const data: MetricNameType[] = res;
      if (data) {
        const metricList: string[] = [];
        for (let i = 0; i < data.length; i++) {
          if (typeof data[i].billable_metric_name !== undefined) {
            metricList.push(data[i].billable_metric_name);
          }
        }
        setMetrics(metricList);
      }
    });
  }, []);

  const mutation = useMutation(
    (data: {
      old_billing_plan_id: string;
      updated_billing_plan: CreatePlanType;
      updateBehavior: string;
    }) =>
      Plan.updatePlan(
        data.old_billing_plan_id,
        data.updated_billing_plan,
        data.updateBehavior
      ),
    {
      onSuccess: () => {
        toast.success("Successfully updated Plan", {
          position: toast.POSITION.TOP_CENTER,
        });
        navigate("/plans");
      },
      onError: () => {
        toast.error("Failed to update Plan", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
    }
  );

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

  const hideFeatureModal = () => {
    setFeatureVisible(false);
  };

  const showFeatureModal = () => {
    setFeatureVisible(true);
  };
  const submitPricingPlan = () => {
    console.log("Submit Pricing Plan");
    form
      .validateFields()
      .then((values) => {
        const usagecomponentslist: CreateComponent[] = [];
        const components = form.getFieldValue("components");
        if (components) {
          for (let i = 0; i < components.length; i++) {
            const usagecomponent: CreateComponent = {
              billable_metric_name: components[i].metric,
              cost_per_batch: components[i].cost_per_batch,
              metric_units_per_batch: components[i].metric_units_per_batch,
              free_metric_units: components[i].free_amount,
              max_metric_units: components[i].max_metric_units,
            };
            usagecomponentslist.push(usagecomponent);
          }
        }

        const newPlan: CreatePlanType = {
          name: values.name,
          description: values.description,
          flat_rate: values.flat_rate,
          pay_in_advance: values.pay_in_advance,
          interval: values.billing_interval,
          components: usagecomponentslist,
        };
        mutation.mutate({
          old_billing_plan_id: plan.billing_plan_id,
          updated_billing_plan: newPlan,
          updateBehavior: values.update_behavior,
        });
        form.resetFields();
      })
      .catch((info) => {
        console.log("Validate Failed:", info);
      });
  };

  return (
    <div className="flex flex-col">
      <PageHeader
        className="site-page-header"
        onBack={goBackPage}
        title="Update Plan"
      />
      <Form.Provider
        onFormFinish={(name, { values, forms }) => {
          if (name === "component_form") {
            const { create_plan } = forms;
            const components = create_plan.getFieldValue("components") || [];
            create_plan.setFieldsValue({ components: [...components, values] });
            setVisible(false);
          }
        }}
      >
        <Form
          form={form}
          name="create_plan"
          onFinish={submitPricingPlan}
          onFinishFailed={onFinishFailed}
          autoComplete="off"
          initialValues={{
            name: plan.name,
            description: plan.description,
            flat_rate: plan.flat_rate,
            pay_in_advance: plan.pay_in_advance,
            billing_interval: plan.interval,
          }}
        >
          <div className="grid grid-cols-2 space-x-4">
            <div className="mx-2 my-2">
              <h2 className="mb-4">Plan Info</h2>
              <Form.Item
                label="Plan Name"
                name="name"
                rules={[
                  {
                    required: true,
                    message: "Please Name Your Plan",
                  },
                ]}
              >
                <Input placeholder="Ex: Starter Plan" />
              </Form.Item>
              <Form.Item label="Description" name="description">
                <Input
                  type="textarea"
                  placeholder="Ex: Cheapest plan for small scale businesses"
                />
              </Form.Item>
              <Form.Item
                label="Billing Interval"
                name="billing_interval"
                rules={[
                  {
                    required: true,
                    message: "Please select an interval",
                  },
                ]}
              >
                <Select>
                  <Select.Option value="week">Weekly</Select.Option>
                  <Select.Option value="month">Monthly</Select.Option>
                  <Select.Option value="year">Yearly</Select.Option>
                </Select>
              </Form.Item>

              <Form.Item name="flat_rate" label="Recurring Cost">
                <InputNumber addonBefore="$" defaultValue={0} precision={2} />
              </Form.Item>
              <Form.Item name="pay_in_advance">
                <Checkbox defaultChecked={true}>Pay In Advance </Checkbox>
              </Form.Item>
              <Form.Item
                name="update_behavior"
                label="When To Update Plan"
                rules={[
                  {
                    required: true,
                    message: "Please select an update behavior",
                  },
                ]}
              >
                <Radio.Group optionType="button" buttonStyle="solid">
                  <Radio value="replace_immediately">Update Immediately</Radio>
                  <Radio value="replace_on_renewal"> Update On Renewal</Radio>
                </Radio.Group>
              </Form.Item>
              <div className="flex flex-row justify-center">
                <Form.Item>
                  <Button
                    htmlType="button"
                    style={{ margin: "0 8px" }}
                    onClick={showUserModal}
                  >
                    Add Component
                  </Button>
                </Form.Item>
                <Form.Item>
                  <Button
                    htmlType="button"
                    style={{ margin: "0 8px" }}
                    onClick={showFeatureModal}
                  >
                    Add Feature(s)
                  </Button>
                </Form.Item>
              </div>
            </div>
            <div className="grid grid-rows-2">
              <div className="flex flex-col space-y-4">
                <h2>Added Components</h2>
                <Form.Item
                  className="self-start"
                  shouldUpdate={(prevValues, curValues) =>
                    prevValues.components !== curValues.components
                  }
                >
                  {({ getFieldValue }) => {
                    const components: ComponentDisplay[] =
                      getFieldValue("components") || [];
                    console.log(components);
                    return components.length ? (
                      <List grid={{ gutter: 16, column: 4 }}>
                        {components.map((component, index) => (
                          <List.Item key={index} className="user">
                            <Card title={component.metric}>
                              <p>
                                <b>Cost:</b> {component.cost_per_batch} per{" "}
                                {component.metric_units_per_batch} events{" "}
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
              </div>

              <div className="flex flex-col space-y-4 overflow-auto">
                <h2>Added Features</h2>
                <Form.Item
                  className="self-start"
                  shouldUpdate={(prevValues, curValues) =>
                    prevValues.components !== curValues.components
                  }
                >
                  <List grid={{ gutter: 16, column: 4 }}>
                    {planFeatures.map((feature, index) => (
                      <List.Item key={index}>
                        <div className="container max-w-sm bg-grey3">
                          <h3>{feature}</h3>
                        </div>
                      </List.Item>
                    ))}
                  </List>
                </Form.Item>
              </div>
            </div>
          </div>

          <Form.Item>
            <Button type="primary" className="bg-info" htmlType="submit">
              Update Plan
            </Button>
          </Form.Item>
        </Form>
        <UsageComponentForm
          visible={visible}
          onCancel={hideUserModal}
          metrics={metrics}
          component={selectedComponent}
        />
      </Form.Provider>
    </div>
  );
};

export default EditPlan;
