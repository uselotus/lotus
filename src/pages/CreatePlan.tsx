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
  Radio,
  Divider,
} from "antd";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import UsageComponentForm from "../components/UsageComponentForm";
import { useMutation } from "react-query";
import { MetricNameType } from "../types/metric-type";
import { toast, ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import { Metrics } from "../api/api";
import { CreatePlanType, CreateComponent } from "../types/plan-type";
import { Plan } from "../api/api";

interface ComponentDisplay {
  metric: string;
  cost_per_metric: number;
  metric_amount_per_cost: number;
  free_amount: number;
}

const CreatePlan = () => {
  const [visible, setVisible] = useState(false);
  const navigate = useNavigate();
  const [metrics, setMetrics] = useState<string[]>([]);
  const [form] = Form.useForm();
  const [metricMap, setMetricMap] = useState<Map<string, number>>(new Map());

  useEffect(() => {
    Metrics.getMetrics().then((res) => {
      const data: MetricNameType[] = res;
      if (data) {
        const newmetricMap = new Map<string, number>();
        const metricList: string[] = [];
        for (let i = 0; i < data.length; i++) {
          if (typeof data[i].metric_name !== undefined) {
            metricList.push(data[i].metric_name);
            newmetricMap.set(data[i].metric_name, data[i].id);
          }
        }
        setMetricMap(newmetricMap);
        setMetrics(metricList);
      }
    });
  }, []);

  const mutation = useMutation(
    (post: CreatePlanType) => Plan.createPlan(post),
    {
      onSuccess: () => {
        toast.success("Successfully created Plan", {
          position: toast.POSITION.TOP_CENTER,
        });
        navigate("/plans");
      },
      onError: () => {
        toast.error("Failed to create Plan", {
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
              billable_metric: metricMap.get(components[i].metric),
              cost_per_metric: components[i].cost_per_metric,
              metric_amount_per_cost: components[i].metric_amount_per_cost,
              free_metric_quantity: components[i].free_amount,
            };
            usagecomponentslist.push(usagecomponent);
          }
        }

        const plan: CreatePlanType = {
          name: values.name,
          description: values.description,
          flat_rate: values.flat_rate,
          pay_in_advance: values.pay_in_advance,
          interval: values.billing_interval,
          components: usagecomponentslist,
        };
        mutation.mutate(plan);
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
        title="Create Plan"
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
          initialValues={{ flat_rate: 0, pay_in_advance: true }}
          onFinish={submitPricingPlan}
          onFinishFailed={onFinishFailed}
          autoComplete="off"
        >
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
          <div className="grid grid-cols-1">
            <div className=" flex flex-col border border-grey1 my-2 mx-2 px-2 py-2 place-items-center	">
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
            </div>
            <Divider type="vertical" />
            <div className=" my-2 mx-2 px-2 py-2"></div>
          </div>

          <Form.Item>
            <Button type="primary" className="bg-info" htmlType="submit">
              Submit
            </Button>
          </Form.Item>
        </Form>
        <UsageComponentForm
          visible={visible}
          onCancel={hideUserModal}
          metrics={metrics}
        />
      </Form.Provider>
      <ToastContainer />
    </div>
  );
};

export default CreatePlan;
