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
  Row,
  Col,
  Divider,
  Radio,
  Affix,
  Space,
} from 'antd'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import UsageComponentForm from '../components/Plans/UsageComponentForm'
import { useMutation, useQuery, UseQueryResult } from 'react-query'
import { MetricNameType } from '../types/metric-type'
import { toast } from 'react-toastify'
import { Features, Metrics } from '../api/api'
import { CreatePlanType, CreateComponent } from '../types/plan-type'
import { Plan } from '../api/api'
import { FeatureType } from '../types/feature-type'
import FeatureForm from '../components/Plans/FeatureForm'
import { DeleteOutlined, ArrowLeftOutlined, SaveOutlined } from '@ant-design/icons'
import React from 'react'

interface ComponentDisplay {
  metric: string
  cost_per_batch: number
  metric_units_per_batch: number
  free_metric_units: number
  max_metric_units: number
}

const CreatePlan = () => {
  const [visible, setVisible] = useState(false)
  const [featureVisible, setFeatureVisible] = useState(false)
  const navigate = useNavigate()
  const [metrics, setMetrics] = useState<string[]>([])
  const [form] = Form.useForm()
  const [planFeatures, setPlanFeatures] = useState<FeatureType[]>([])

  const addFeatures = (newFeatures: FeatureType[]) => {
    setPlanFeatures([...planFeatures, ...newFeatures])
    setFeatureVisible(false)
  }

  useEffect(() => {
    Metrics.getMetrics().then((res) => {
      const data: MetricNameType[] = res
      if (data) {
        const metricList: string[] = []
        for (let i = 0; i < data.length; i++) {
          if (typeof data[i].billable_metric_name !== undefined) {
            metricList.push(data[i].billable_metric_name)
          }
        }
        setMetrics(metricList)
      }
    })
  }, [])

  const {
    data: features,
    isLoading,
    isError,
  }: UseQueryResult<FeatureType[]> = useQuery<FeatureType[]>(['feature_list'], () =>
    Features.getFeatures().then((res) => {
      return res
    }),
  )

  const mutation = useMutation((post: CreatePlanType) => Plan.createPlan(post), {
    onSuccess: () => {
      toast.success('Successfully created Plan', {
        position: toast.POSITION.TOP_CENTER,
      })
      form.resetFields()
      navigate('/plans')
    },
    onError: () => {
      toast.error('Failed to create Plan', {
        position: toast.POSITION.TOP_CENTER,
      })
    },
  })
  const removeFeature = (e) => {
    const name = e.target.getAttribute('name')
    setPlanFeatures(planFeatures.filter((item) => item.feature_name !== name))
  }

  const onFinishFailed = (errorInfo: any) => {}

  const hideUserModal = () => {
    setVisible(false)
  }

  const showUserModal = () => {
    setVisible(true)
  }

  const hideFeatureModal = () => {
    setFeatureVisible(false)
  }

  const showFeatureModal = () => {
    setFeatureVisible(true)
  }

  const goBackPage = () => {
    navigate(-1)
  }

  const submitPricingPlan = () => {
    form
      .validateFields()
      .then((values) => {
        const usagecomponentslist: CreateComponent[] = []
        const components = form.getFieldValue('components')
        if (components) {
          for (let i = 0; i < components.length; i++) {
            const usagecomponent: CreateComponent = {
              billable_metric_name: components[i].metric,
              cost_per_batch: components[i].cost_per_batch,
              metric_units_per_batch: components[i].metric_units_per_batch,
              free_metric_units: components[i].free_amount,
              max_metric_units: components[i].max_metric_units,
            }
            usagecomponentslist.push(usagecomponent)
          }
        }

        const plan: CreatePlanType = {
          name: values.name,
          description: values.description,
          flat_rate: values.flat_rate,
          pay_in_advance: values.pay_in_advance,
          interval: values.billing_interval,
          components: usagecomponentslist,
          features: planFeatures,
        }
        mutation.mutate(plan)
      })
      .catch((info) => {
        console.log('Validate Failed:', info)
      })
  }

  return (
    <div className='flex flex-col'>
      <PageHeader
        title='Create Plan'
        extra={[
          <Button onClick={goBackPage} icon={<ArrowLeftOutlined />} type='default' size='large'>
            Back
          </Button>,
          <Button
            onClick={goBackPage}
            className='bg-black text-white justify-self-end'
            size='large'
          >
            Create Plan <SaveOutlined />
          </Button>,
        ]}
      />
      <Form.Provider
        onFormFinish={(name, { values, forms }) => {
          if (name === 'component_form') {
            const { create_plan } = forms
            const components = create_plan.getFieldValue('components') || []
            create_plan.setFieldsValue({ components: [...components, values] })
            setVisible(false)
          }
        }}
      >
        <Form
          form={form}
          name='create_plan'
          initialValues={{ flat_rate: 0, pay_in_advance: true }}
          onFinish={submitPricingPlan}
          onFinishFailed={onFinishFailed}
          autoComplete='off'
          labelCol={{ span: 8 }}
          wrapperCol={{ span: 16 }}
          labelAlign='left'
        >
          <Row gutter={24}>
            <Col span={12}>
              <Row gutter={[24, 24]}>
                <Col span='24'>
                  <Card title='Plan Information'>
                    <Form.Item
                      label='Plan Name'
                      name='name'
                      rules={[
                        {
                          required: true,
                          message: 'Please Name Your Plan',
                        },
                      ]}
                    >
                      <Input placeholder='Ex: Starter Plan' />
                    </Form.Item>
                    <Form.Item label='Description' name='description'>
                      <Input
                        type='textarea'
                        placeholder='Ex: Cheapest plan for small scale businesses'
                      />
                    </Form.Item>
                    <Form.Item
                      label='Billing Interval'
                      name='billing_interval'
                      rules={[
                        {
                          required: true,
                          message: 'Please select an interval',
                        },
                      ]}
                    >
                      <Radio.Group>
                        <Radio value='week'>Weekly</Radio>
                        <Radio value='month'>Monthly</Radio>
                        <Radio value='yearly'>Yearly</Radio>
                      </Radio.Group>
                    </Form.Item>

                    <Form.Item name='flat_rate' label='Recurring Cost'>
                      <InputNumber addonBefore='$' defaultValue={0} precision={2} />
                    </Form.Item>
                    <Form.Item name='pay_in_advance' label='Pay In Advance'>
                      <Checkbox defaultChecked={true} />
                    </Form.Item>
                  </Card>
                </Col>
                <Col span='24'>
                  <Card
                    title='Added Features'
                    extra={[
                      <Button htmlType='button' onClick={showFeatureModal}>
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
                      <Row gutter={[12, 12]}>
                        {planFeatures.map((feature, index) => (
                          <Col key={index} span={24}>
                            <Card bodyStyle={{ backgroundColor: '#CCA43B69' }}>
                              <h3 className='justify-self-center'>
                                {feature.feature_name} <DeleteOutlined />
                              </h3>
                            </Card>
                          </Col>
                        ))}
                      </Row>
                    </Form.Item>
                  </Card>
                </Col>
              </Row>
            </Col>

            <Col span={12}>
              <Row gutter={[24, 24]}>
                <Col span={24}>
                  <Card
                    title='Added Components'
                    extra={[
                      <Button htmlType='button' onClick={showUserModal}>
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
                      {({ getFieldValue }) => {
                        const components: ComponentDisplay[] = getFieldValue('components') || []
                        console.log(components)

                        return components.length ? (
                          <Row gutter={[12, 12]}>
                            {components.map((component, index) => (
                              <Col span='12'>
                                <Card type='inner' bodyStyle={{ backgroundColor: '#F7F8FD' }}>
                                  <h3>{component.metric}</h3>
                                  <p>
                                    <b>Cost:</b> ${component.cost_per_batch} per{' '}
                                    {component.metric_units_per_batch}{' '}
                                    {component.metric_units_per_batch === 1 ? 'unit' : 'units'}{' '}
                                  </p>
                                  <br />
                                  <p>
                                    <b>Free Units:</b> {component.free_metric_units}
                                  </p>
                                  <p>
                                    <b>Max Units:</b> {component.max_metric_units}
                                  </p>
                                </Card>
                              </Col>
                            ))}
                          </Row>
                        ) : null
                      }}
                    </Form.Item>
                  </Card>
                </Col>
              </Row>
            </Col>
          </Row>
          {/* <div className='absolute bottom-20 right-10 '>
            <Form.Item>
              <Button type='primary' className='bg-black justify-self-end' htmlType='submit'>
                Submit
              </Button>
            </Form.Item>
          </div> */}
        </Form>
        <UsageComponentForm visible={visible} onCancel={hideUserModal} metrics={metrics} />
        <FeatureForm
          visible={featureVisible}
          onCancel={hideFeatureModal}
          features={features}
          onAddFeatures={addFeatures}
        />
      </Form.Provider>
    </div>
  )
}

export default CreatePlan
