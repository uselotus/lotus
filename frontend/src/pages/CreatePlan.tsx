import {
  Button,
  Checkbox,
  Form,
  Card,
  Input,
  InputNumber,
  Row,
  Col,
  Radio,
  Descriptions,
} from "antd";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import UsageComponentForm from "../components/Plans/UsageComponentForm";
import { useMutation, useQuery, useQueryClient } from "react-query";
import { toast } from "react-toastify";

import {
  CreatePlanType,
  CreateComponent,
  CreateInitialVersionType,
} from "../types/plan-type";
import { Plan } from "../api/api";
import { FeatureType } from "../types/feature-type";
import FeatureForm from "../components/Plans/FeatureForm";
import {
  DeleteOutlined,
  ArrowLeftOutlined,
  SaveOutlined,
  EditOutlined,
} from "@ant-design/icons";
import React from "react";
import { Paper } from "../components/base/Paper";
import { PageLayout } from "../components/base/PageLayout";
import { ComponentDisplay } from "../components/Plans/ComponentDisplay";
import FeatureDisplay from "../components/Plans/FeatureDisplay";

interface ComponentDisplay {
  metric: string;
  cost_per_batch: number;
  metric_units_per_batch: number;
  free_metric_units: number;
  max_metric_units: number;
  id: number;
}

const CreatePlan = () => {
  const [componentVisible, setcomponentVisible] = useState<boolean>();
  const [featureVisible, setFeatureVisible] = useState<boolean>(false);
  const navigate = useNavigate();
  const [componentsData, setComponentsData] = useState<any>([]);
  const [form] = Form.useForm();
  const [planFeatures, setPlanFeatures] = useState<FeatureType[]>([]);
  const [editComponentItem, setEditComponentsItem] = useState<any>();
  const queryClient = useQueryClient();

  const mutation = useMutation(
    (post: CreatePlanType) => Plan.createPlan(post),
    {
      onSuccess: () => {
        toast.success("Successfully created Plan", {
          position: toast.POSITION.TOP_CENTER,
        });
        form.resetFields();
        queryClient.invalidateQueries(["plan_list"]);
        navigate("/plans");
      },
      onError: () => {
        toast.error("Failed to create Plan", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
    }
  );

  const addFeatures = (newFeatures: FeatureType[]) => {
    for (let i = 0; i < newFeatures.length; i++) {
      if (
        planFeatures.some(
          (feat) => feat.feature_name === newFeatures[i].feature_name
        )
      ) {
      } else {
        setPlanFeatures((prev) => [...prev, newFeatures[i]]);
      }
    }
    setFeatureVisible(false);
  };

  const editFeatures = (feature_name: string) => {
    const currentFeature = planFeatures.filter(
      (item) => item.feature_name === feature_name
    )[0];
    setFeatureVisible(true);
  };

  const removeFeature = (feature_name: string) => {
    setPlanFeatures(
      planFeatures.filter((item) => item.feature_name !== feature_name)
    );
  };

  const onFinishFailed = (errorInfo: any) => {};

  const hideComponentModal = () => {
    setcomponentVisible(false);
  };

  const showComponentModal = () => {
    setcomponentVisible(true);
  };

  const handleComponentAdd = (newData: any) => {
    const old = componentsData;
    console.log("editComponentItem", editComponentItem);

    if (editComponentItem) {
      const index = componentsData.findIndex(
        (item) => item.id === editComponentItem.id
      );
      old[index] = newData;
      setComponentsData(old);
    } else {
      const newComponentsData = [
        ...old,
        {
          ...newData,
          id: Math.floor(Math.random() * 1000),
        },
      ];
      setComponentsData(newComponentsData);
    }
    setEditComponentsItem(undefined);
    setcomponentVisible(false);
  };

  const handleComponentEdit = (id: any) => {
    const currentComponent = componentsData.filter((item) => item.id === id)[0];

    setEditComponentsItem(currentComponent);
    setcomponentVisible(true);
  };

  const deleteComponent = (id: number) => {
    setComponentsData(componentsData.filter((item) => item.id !== id));
  };
  const hideFeatureModal = () => {
    setFeatureVisible(false);
  };

  const showFeatureModal = () => {
    setFeatureVisible(true);
  };

  const goBackPage = () => {
    navigate(-1);
  };

  const submitPricingPlan = () => {
    form
      .validateFields()
      .then((values) => {
        const usagecomponentslist: CreateComponent[] = [];
        const components: any = Object.values(componentsData);
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

        const initialPlanVersion: CreateInitialVersionType = {
          description: values.description,
          flat_fee_billing_type: values.pay_in_advance,
          flat_rate: values.flat_rate,
          components: usagecomponentslist,
          features: planFeatures,
          usage_billing_type: values.usage_billing_type,
        };

        const plan: CreatePlanType = {
          plan_name: values.name,
          plan_duration: values.billing_interval,
          initial_version: values.pay_in_advance,
        };
        mutation.mutate(plan);
      })
      .catch((info) => {
        console.log("Validate Failed:", info);
      });
  };

  return (
    <PageLayout
      title="Create Plan"
      extra={[
        <Button
          key={"back"}
          onClick={goBackPage}
          icon={<ArrowLeftOutlined />}
          type="default"
          size="large"
        >
          Back
        </Button>,
        <Button
          key="create"
          onClick={() => form.submit()}
          // className="bg-black text-white justify-self-end"
          size="large"
          type="primary"
        >
          Create Plan <SaveOutlined />
        </Button>,
      ]}
    >
      <Form.Provider>
        <Form
          form={form}
          name="create_plan"
          initialValues={{ flat_rate: 0, pay_in_advance: true }}
          onFinish={submitPricingPlan}
          onFinishFailed={onFinishFailed}
          autoComplete="off"
          labelCol={{ span: 8 }}
          wrapperCol={{ span: 16 }}
          labelAlign="left"
        >
          <Row gutter={24}>
            <Col span={12}>
              <Row gutter={[24, 24]}>
                <Col span="24">
                  <Card title="Plan Information">
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
                      <Radio.Group>
                        <Radio value="week">Weekly</Radio>
                        <Radio value="month">Monthly</Radio>
                        <Radio value="year">Yearly</Radio>
                      </Radio.Group>
                    </Form.Item>

                    <Form.Item name="flat_rate" label="Recurring Cost">
                      <InputNumber
                        addonBefore="$"
                        defaultValue={0}
                        precision={2}
                      />
                    </Form.Item>
                    <Form.Item name="pay_in_advance" label="Pay In Advance">
                      <Checkbox defaultChecked={true} />
                    </Form.Item>
                  </Card>
                </Col>
                <Col span="24">
                  <Card
                    title="Added Features"
                    extra={[
                      <Button htmlType="button" onClick={showFeatureModal}>
                        Add Feature
                      </Button>,
                    ]}
                  >
                    <Form.Item
                      wrapperCol={{ span: 24 }}
                      shouldUpdate={(prevValues, curValues) =>
                        prevValues.components !== curValues.components
                      }
                    >
                      <FeatureDisplay
                        planFeatures={planFeatures}
                        removeFeature={removeFeature}
                        editFeatures={editFeatures}
                      />
                    </Form.Item>
                  </Card>
                </Col>
              </Row>
            </Col>

            <Col span={12}>
              <Row gutter={[24, 24]}>
                <Col span={24}>
                  <Card
                    title="Added Components"
                    extra={[
                      <Button
                        htmlType="button"
                        onClick={() => showComponentModal()}
                      >
                        Add Component
                      </Button>,
                    ]}
                  >
                    <Form.Item
                      wrapperCol={{ span: 24 }}
                      shouldUpdate={(prevValues, curValues) =>
                        prevValues.components !== curValues.components
                      }
                    >
                      <ComponentDisplay
                        componentsData={componentsData}
                        handleComponentEdit={handleComponentEdit}
                        deleteComponent={deleteComponent}
                      />
                    </Form.Item>
                  </Card>
                </Col>
              </Row>
            </Col>
          </Row>
        </Form>
        {componentVisible && (
          <UsageComponentForm
            visible={componentVisible}
            onCancel={hideComponentModal}
            componentsData={componentsData}
            handleComponentAdd={handleComponentAdd}
            editComponentItem={editComponentItem}
            setEditComponentsItem={setEditComponentsItem}
          />
        )}
        {featureVisible && (
          <FeatureForm
            visible={featureVisible}
            onCancel={hideFeatureModal}
            onAddFeatures={addFeatures}
          />
        )}
      </Form.Provider>
    </PageLayout>
  );
};

export default CreatePlan;
