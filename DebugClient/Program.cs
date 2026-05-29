using DebugClient.Components;
using DebugClient.Services;

var builder = WebApplication.CreateBuilder(args);

// Belt mic services: the UDP receiver runs as a singleton hosted service
// so it keeps streaming regardless of how many browser tabs are open.
builder.Services.Configure<BeltOptions>(builder.Configuration.GetSection("Belt"));
builder.Services.AddSingleton<MicReceiver>();
builder.Services.AddHostedService(sp => sp.GetRequiredService<MicReceiver>());

// Add CORS for Python analysis pipeline
builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(policy =>
    {
        policy.AllowAnyOrigin()
             .AllowAnyMethod()
             .AllowAnyHeader();
    });
});

// Add services to the container.
builder.Services.AddControllers();
builder.Services.AddRazorComponents()
    .AddInteractiveServerComponents();

var app = builder.Build();

// Configure the HTTP request pipeline.
if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Error", createScopeForErrors: true);
    // The default HSTS value is 30 days. You may want to change this for production scenarios, see https://aka.ms/aspnetcore-hsts.
    app.UseHsts();
}

app.UseStatusCodePagesWithReExecute("/not-found", createScopeForStatusCodePages: true);
app.UseHttpsRedirection();

app.UseCors();

app.UseAntiforgery();

app.MapStaticAssets();
app.MapControllers();
app.MapRazorComponents<App>()
    .AddInteractiveServerRenderMode();

app.Run();
